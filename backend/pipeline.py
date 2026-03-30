import os
import json
from jira import JIRA

from schemas import ExecuteRequest
from workspace import WorkspaceManager
from qa_tools import run_shell_command, execute_tests_and_save_coverage
from agents import run_developer_agent, run_reviewer_agent, run_test_engineer_agent

def _build_current_files_context(workspace: WorkspaceManager, saved_files: list) -> str:
    """
    Helper function for Self-Healing: Reads the files the Developer just generated and feeds 
    them back into the prompt so the LLM can modify them in place instead of creating redundant files.
    """
    if not saved_files: return ""
    
    context = "\n\n### YOUR CURRENT IMPLEMENTATION (MODIFY THESE FILES) ###\n"
    for f_path in saved_files:
        full_path = os.path.join(workspace.repo_path, f_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            context += f"---FILE: {f_path}---\n{content}\n---END---\n"
    return context

def run_multi_agent_loop(request: ExecuteRequest, session: dict, workspace: WorkspaceManager, enable_code_review: bool = True):
    """
    The Core Orchestrator: Chains together the Developer and Reviewer agents in a robust 
    feedback loop.
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
        print(f"\n🔄 --- PIPELINE ATTEMPT {attempt}/{max_attempts} ---")
        
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

        # Pipeline success
        break

    return saved_files, True, pipeline_logs

def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    """
    Asynchronous background task. Builds the feature branch, opens a PR, 
    and then spins off a separate testing branch to write and execute unit tests.
    """
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        # 1. Execute the primary Feature Loop
        saved_files, _, pipeline_logs = run_multi_agent_loop(request, session, workspace, enable_code_review=True)

        # 2. Push Feature Branch
        workspace.ensure_gitignore()
        workspace.run_git_command("add", ".")
        status_check = workspace.run_git_command("status", "--porcelain", check=False)
        
        if status_check.stdout.strip():
            workspace.run_git_command("commit", "-m", f"Auto-implemented {request.ticket_id}")
            workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
        else:
            print("⏭️ No code changes detected by Git. Pushing existing branch state.")
            workspace.run_git_command("push", "--set-upstream", "origin", branch_name, check=False)
            
        pr_body = f"""### 🤖 VibeCoder AI Implementation
        Resolves Jira Ticket: **{request.ticket_id}**

        **Details:**
        * Strategy: {request.plan.get('strategy', 'N/A')}
        * Reviewer Approved: Yes ✅
        * *Note: Unit tests and coverage report are being generated on the `{branch_name}-testing` branch.*
        """
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id} Implementation", pr_body)
        print(f"✨ FEATURE PR OPENED: {pr_url}")

        # ==========================================
        # 3. POST-PUSH TESTING PHASE (Separate Branch)
        # ==========================================
        print(f"\n🧪 Initiating Post-Push Testing Phase...")
        test_branch_name = workspace.create_testing_branch(branch_name)
        
        # Grab the current code context to feed to the Test Engineer
        current_code = _build_current_files_context(workspace, saved_files)
        
        # Generate Markdown plan, test files, and command
        test_cmd, test_files = run_test_engineer_agent(
            request.ticket_id, 
            workspace.get_repo_tree(), 
            current_code, 
            workspace.repo_path
        )
        
        # Execute tests and dump to coverage_report.txt
        execute_tests_and_save_coverage(test_cmd, workspace.repo_path)
        
        # Push the Testing Branch
        workspace.run_git_command("add", ".")
        test_status = workspace.run_git_command("status", "--porcelain", check=False)
        
        if test_status.stdout.strip():
            workspace.run_git_command("commit", "-m", f"Add test cases, unit tests, and coverage report for {request.ticket_id}")
            workspace.run_git_command("push", "--set-upstream", "origin", test_branch_name)
            print(f"🎯 TESTING PHASE COMPLETE! Artifacts pushed to branch: {test_branch_name}")
        else:
            print("⚠️ No test artifacts were generated.")
            
    except Exception as e:
        print(f"🔥 FATAL ERROR IN BACKGROUND AGENT WORKER: {str(e)}")