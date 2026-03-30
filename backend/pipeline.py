import os
import json
from jira import JIRA
import requests

from schemas import ExecuteRequest
from workspace import WorkspaceManager
from qa_tools import run_shell_command, execute_tests_and_save_coverage
from agents import run_developer_agent, run_reviewer_agent, run_test_engineer_agent, run_devops_agent, run_pr_webhook_reviewer

def _build_current_files_context(workspace: WorkspaceManager, saved_files: list) -> str:
    """Helper function to feed the current files back into the prompt for in-place modification."""
    if not saved_files: return ""
    
    context = "\n\n### YOUR CURRENT IMPLEMENTATION (MODIFY THESE FILES) ###\n"
    for f_path in saved_files:
        full_path = os.path.join(workspace.repo_path, f_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            context += f"---FILE: {f_path}---\n{content}\n---END---\n"
    return context

def run_multi_agent_loop(request: ExecuteRequest, session: dict, workspace: WorkspaceManager, enable_code_review: bool = True, ci_feedback: str = ""):
    """
    The Core Orchestrator: Chains together the Developer and Reviewer agents.
    If CI failed on a previous push, it injects those logs via ci_feedback.
    """
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(request.ticket_id)
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    
    print("\n⚙️ --- PRE-FLIGHT SETUP ---")
    setup_commands = request.plan.get("commands_to_run", [])
    setup_logs = ""
    
    for cmd in setup_commands: 
        if cmd.strip(): 
            print(f"🚀 Executing Architect Command: {cmd}")
            success, output = run_shell_command(cmd, workspace.repo_path, timeout=300)
            setup_logs += f"\n$ {cmd}\n{output}\n"

    base_developer_prompt = f"""
    You are the Lead Developer Agent. Implement this approved plan.
    JIRA TICKET:\n{jira_context}
    
    APPROVED PLAN:\n{json.dumps(request.plan, indent=2)}
    
    PRE-FLIGHT COMMAND LOGS:
    {setup_logs if setup_logs else "No setup commands ran."}
    
    CURRENT REPOSITORY STRUCTURE:\n{workspace.get_repo_tree()}
    
    {ci_feedback}
    
    CRITICAL INSTRUCTIONS: 
    1. ANTI-LAZINESS: You MUST generate the complete, fully-functioning code for EVERY SINGLE FILE listed in the plan.
    2. Do NOT leave TODOs or placeholders. Write production-ready code.
    3. DO NOT wrap the code in markdown code blocks (e.g., ```javascript). 
    
    EXAMPLE OUTPUT FORMAT:
    ---FILE: path/to/the/file.ext---
    // your raw functional code goes here
    ---END---
    """
    
    developer_prompt = base_developer_prompt
    max_attempts = 4 
    saved_files = []
    pipeline_logs = []

    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 --- LOCAL PIPELINE ATTEMPT {attempt}/{max_attempts} ---")
        
        # --- 1. DEVELOPER PHASE ---
        try:
            run_developer_agent(developer_prompt, workspace.repo_path, saved_files)
            if not saved_files: raise ValueError("Developer Agent failed to generate files.")
        except ValueError as e:
            print(f"⚠️ Developer Phase Failed: {e}")
            pipeline_logs.append(f"Developer Error: {str(e)}")
            developer_prompt = base_developer_prompt + f"\n\n🚨 URGENT: Previous attempt failed ({e}). Please provide a concise, optimized response."
            continue

        # --- 2. REVIEWER PHASE (Deep Static Analysis) ---
        if enable_code_review:
            try:
                diff_text = "".join([f"\n--- FILE: {d['file']} ---\nNEW CODE:\n{d['new_content']}\n" for d in workspace.get_file_diffs(saved_files)])
                
                is_approved, review_text = run_reviewer_agent(
                    request.ticket_id, 
                    jira_context, 
                    workspace.get_repo_tree(),
                    diff_text
                )
                pipeline_logs.append(f"Code Review: {review_text}")

                if not is_approved:
                    print("⚠️ Senior Reviewer requested changes. Bouncing back to Developer...")
                    current_code = _build_current_files_context(workspace, saved_files)
                    developer_prompt = base_developer_prompt + current_code + f"\n\n🚨 URGENT - CODE REVIEWER REJECTED YOUR CODE:\nREVIEWER FEEDBACK:\n{review_text}\nFix the issues and output the corrected files using the EXACT SAME FILE PATHS."
                    continue 
                
                print("✅ Senior Reviewer approved the code and verified ticket scope!")
            except ValueError as e:
                print(f"⚠️ Reviewer Phase Failed: {e}")
                pipeline_logs.append(f"Reviewer Error: {str(e)}")
                continue

        break

    return saved_files, True, pipeline_logs

def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    """
    Asynchronous background task utilizing Remote CI/CD Multi-Layered Feedback.
    """
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        # ==========================================
        # 0. DEVOPS PHASE: Setup Remote CI/CD
        # ==========================================
        run_devops_agent(workspace.get_repo_tree(), workspace.repo_path)

        max_ci_attempts = 2
        ci_feedback = ""
        ci_success = True
        final_saved_files = []

        # ==========================================
        # THE REMOTE FEEDBACK LOOP
        # ==========================================
        for ci_attempt in range(1, max_ci_attempts + 1):
            print(f"\n🚀 === REMOTE CI PIPELINE ATTEMPT {ci_attempt}/{max_ci_attempts} ===")
            
            # 1. Execute the primary Feature Loop (Developer + Reviewer)
            saved_files, _, pipeline_logs = run_multi_agent_loop(
                request, session, workspace, enable_code_review=True, ci_feedback=ci_feedback
            )
            final_saved_files = saved_files

            # 2. Push Feature Branch (including the DevOps .github/workflow file)
            workspace.ensure_gitignore()
            workspace.run_git_command("add", ".")
            status_check = workspace.run_git_command("status", "--porcelain", check=False)
            
            if status_check.stdout.strip():
                workspace.run_git_command("commit", "-m", f"VibeCoder implementation (Attempt {ci_attempt}) for {request.ticket_id}")
                workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
            else:
                print("⏭️ No code changes detected by Git. Pushing existing branch state.")
                workspace.run_git_command("push", "--set-upstream", "origin", branch_name, check=False)
                
            # 3. Poll GitHub Actions for Remote Feedback
            ci_result = workspace.wait_for_ci_and_get_logs(branch_name)
            
            if ci_result["success"]:
                print("🎉 Remote CI passed! Feature is fully validated.")
                ci_success = True
                break
            else:
                print("❌ Remote CI failed! Gathering logs for self-healing...")
                ci_success = False
                if ci_attempt < max_ci_attempts:
                    # Feed the failing CI logs back into the Developer's prompt for the next loop
                    current_code = _build_current_files_context(workspace, saved_files)
                    ci_feedback = f"\n\n🚨 URGENT - REMOTE CI PIPELINE FAILED ON GITHUB:\n{ci_result['logs']}\n{current_code}\nFix the identified integration/testing issues and output the corrected files."

        # ==========================================
        # 4. OPEN PULL REQUEST
        # ==========================================
        pr_body = f"""### 🤖 VibeCoder AI Implementation
        Resolves Jira Ticket: **{request.ticket_id}**

        **Details:**
        * Strategy: {request.plan.get('strategy', 'N/A')}
        * Reviewer Approved: Yes ✅
        * Remote CI Passed: {'Yes ✅' if ci_success else 'No ❌ (See Action Logs)'}
        * *Note: Unit tests and coverage report are being generated on the `{branch_name}-testing` branch.*
        """
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id} Implementation", pr_body)
        print(f"✨ FEATURE PR OPENED: {pr_url}")
            
    except Exception as e:
        print(f"🔥 FATAL ERROR IN BACKGROUND AGENT WORKER: {str(e)}")

def async_pr_reviewer_worker(payload: dict, session: dict):
    """Fetches the PR diff from GitHub, generates a review, and posts it as a comment."""
    pr_number = payload["pull_request"]["number"]
    pr_title = payload["pull_request"]["title"]
    pr_body = payload["pull_request"]["body"]
    repo_full_name = payload["repository"]["full_name"]
    diff_url = payload["pull_request"]["diff_url"]
    
    github_token = session["github_token"]
    headers = {"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3.diff"}
    
    try:
        # 1. Fetch the raw diff from GitHub
        diff_response = requests.get(diff_url, headers=headers)
        if diff_response.status_code != 200:
            print(f"⚠️ PR Bot failed to fetch diff: {diff_response.status_code}")
            return
            
        diff_text = diff_response.text[:10000] # Cap diff size to save context tokens
        
        # 2. Generate the Review Comment
        review_comment = run_pr_webhook_reviewer(pr_title, pr_body, diff_text)
        
        # 3. Post the comment to the GitHub PR via the REST API
        comment_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
        api_headers = {"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3+json"}
        requests.post(comment_url, json={"body": review_comment}, headers=api_headers)
        
        print(f"✅ PR Bot successfully posted a review on PR #{pr_number}!")
    except Exception as e:
        print(f"🔥 Async PR Reviewer Error: {str(e)}")

def async_test_generation_worker(payload: dict, session: dict):
    """Checks out the newly created PR branch and spins up the Test Engineer pipeline."""
    branch_name = payload["pull_request"]["head"]["ref"]
    ticket_id = branch_name.split("-")[1] if "-" in branch_name else "UNKNOWN"
    
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    try:
        # 1. Prep the workspace on the new feature branch
        workspace.setup_workspace()
        workspace.checkout_base_branch(branch_name)
        
        print(f"\n🧪 Webhook triggered Post-Push Testing Phase for branch {branch_name}...")
        test_branch_name = workspace.create_testing_branch(branch_name)
        
        # We simulate the saved_files context by looking at what changed in the last commit
        diff_check = workspace.run_git_command("diff", "--name-only", f"origin/{session.get('base_branch', 'main')}...{branch_name}")
        saved_files = diff_check.stdout.strip().split("\n")
        current_code = _build_current_files_context(workspace, saved_files)
        
        # 2. Generate and Execute Tests
        test_cmd, test_files = run_test_engineer_agent(ticket_id, workspace.get_repo_tree(), current_code, workspace.repo_path)
        execute_tests_and_save_coverage(test_cmd, workspace.repo_path)
        
        # 3. Commit and Push Test Branch
        workspace.run_git_command("add", ".")
        test_status = workspace.run_git_command("status", "--porcelain", check=False)
        
        if test_status.stdout.strip():
            workspace.run_git_command("commit", "-m", f"Automated test coverage for {branch_name}")
            workspace.run_git_command("push", "--set-upstream", "origin", test_branch_name)
            
            # 4. Open the Secondary PR Targeting the Feature Branch
            test_pr_body = f"### 🧪 Automated Test Suite\nThis PR contains the generated test plan and unit tests for `{branch_name}`."
            workspace.create_pull_request(
                target_branch=test_branch_name, 
                base_branch=branch_name, 
                title=f"Test Coverage: {branch_name}", 
                body=test_pr_body
            )
            print(f"🎯 ASYNC TESTING PHASE COMPLETE! Artifacts pushed to branch: {test_branch_name}")
        else:
            print("⚠️ Async Testing Phase generated no new artifacts.")
            
    except Exception as e:
        print(f"🔥 Async Test Generation Error: {str(e)}")