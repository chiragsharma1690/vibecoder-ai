import os
import json
from jira import JIRA

from schemas import ExecuteRequest
from workspace import WorkspaceManager
from qa_tools import run_shell_command, run_qa_tests, capture_dev_screenshot
from agents import run_developer_agent, generate_qa_command, run_reviewer_agent

def run_multi_agent_loop(request: ExecuteRequest, session: dict, workspace: WorkspaceManager, 
                         enable_qa: bool = True, enable_code_review: bool = True):
    """Orchestrates the Developer, QA, and Reviewer."""
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(request.ticket_id)
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    
    # 🚨 FIX: Save this as the BASE prompt so it never gets erased
    base_developer_prompt = f"""
    You are the Lead Developer Agent. Implement this approved plan.
    JIRA TICKET:\n{jira_context}\nAPPROVED PLAN:\n{json.dumps(request.plan, indent=2)}
    CURRENT REPOSITORY STRUCTURE:\n{workspace.get_repo_tree()}
    
    INSTRUCTIONS: 
    Write the code. Respond ONLY with files formatted exactly as shown below. 
    DO NOT wrap the content in markdown code blocks (e.g., ```javascript or ```python).
    ---FILE: path/to/file.ext---
    content
    ---END---
    """
    
    developer_prompt = base_developer_prompt
    max_attempts = 4 
    saved_files = []
    qa_passed = False
    qa_logs = []
    last_qa_error = "" 

    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 --- PIPELINE ATTEMPT {attempt}/{max_attempts} ---")
        
        # 1. DEVELOPER PHASE
        run_developer_agent(developer_prompt, workspace.repo_path, saved_files)
        if not saved_files: raise ValueError("Developer Agent failed to generate files.")

        if attempt == 1:
            for cmd in request.plan.get("commands_to_run", []): 
                if cmd.strip(): run_shell_command(cmd, workspace.repo_path)

        # 2. QA PHASE
        if enable_qa:
            test_cmd = generate_qa_command(saved_files, workspace.get_repo_tree(), workspace.repo_path, last_qa_error)
            qa_success, qa_output = run_qa_tests(test_cmd, workspace.repo_path)
            qa_logs.append(f"QA Execution: {qa_output}")

            if not qa_success:
                print(f"❌ QA Check Failed. Self-healing...")
                last_qa_error = qa_output
                # 🚨 FIX: Append to the base prompt instead of overwriting!
                developer_prompt = base_developer_prompt + f"\n\n🚨 URGENT - TEST EXECUTION FAILED:\n{qa_output}\nFix the code to pass with >80% coverage. Output the corrected files."
                continue 
            
            print("🎉 QA Agent approved the tests!")
            last_qa_error = ""
        else:
            qa_passed = True

        # 3. REVIEWER PHASE
        if enable_code_review:
            diff_text = "".join([f"\n--- FILE: {d['file']} ---\nNEW CODE:\n{d['new_content']}\n" for d in workspace.get_file_diffs(saved_files)])
            is_approved, review_text = run_reviewer_agent(request.ticket_id, diff_text)
            qa_logs.append(f"Code Review: {review_text}")

            if not is_approved:
                print("⚠️ Senior Reviewer requested changes. Self-healing...")
                # 🚨 FIX: Append to the base prompt instead of overwriting!
                developer_prompt = base_developer_prompt + f"\n\n🚨 URGENT - CODE REVIEWER REJECTED YOUR CODE:\nREVIEWER FEEDBACK:\n{review_text}\nFix the issues and output the corrected files without using markdown code blocks."
                continue 
            
            print("✅ Senior Reviewer approved the code!")

        qa_passed = True
        break

    return saved_files, qa_passed, qa_logs

def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    """The asynchronous PR generation task."""
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        # Run Pipeline
        saved_files, qa_passed, qa_logs = run_multi_agent_loop(request, session, workspace, enable_qa=True, enable_code_review=True)

        workspace.ensure_gitignore()
        ui_components = request.plan.get("ui_components_to_screenshot", [{"route": "/", "selector": "body"}])
        screenshot_paths = capture_dev_screenshot(workspace.repo_path, components=ui_components, port=5174)

        # 🚨 FIX: Check for changes before committing to prevent CalledProcessError
        workspace.run_git_command("add", ".")
        status_check = workspace.run_git_command("status", "--porcelain", check=False)
        
        if status_check.stdout.strip():
            workspace.run_git_command("commit", "-m", f"Auto-implemented {request.ticket_id}")
            workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
        else:
            print("⏭️ No code changes detected by Git. Pushing existing branch state.")
            # We still push in case a branch was created locally but not on remote
            workspace.run_git_command("push", "--set-upstream", "origin", branch_name, check=False)
            
        owner_repo = workspace.repo_url.replace("https://github.com/", "").replace(".git", "")
        screenshots_md = "".join([f"![UI Preview](https://raw.githubusercontent.com/{owner_repo}/{branch_name}/{path})\n<br/>\n" for path in screenshot_paths])
        
        coverage_md = ""
        cov_path = os.path.join(workspace.repo_path, ".agent", "coverage.txt")
        if os.path.exists(cov_path):
            with open(cov_path, "r", encoding="utf-8") as f:
                cov_text = f.read()[-1500:] 
            coverage_md = f"<details><summary>📊 Test Coverage Report</summary>\n\n```text\n{cov_text}\n```\n</details>"
        
        pr_body = f"""### 🤖 VibeCoder AI Implementation
Resolves Jira Ticket: **{request.ticket_id}**\n
**Details:**
* Strategy: {request.plan.get('strategy', 'N/A')}
* Pipeline Passed: {'Yes ✅' if qa_passed else 'Failed / Skipped ⚠️'} \n
{coverage_md}\n
**📸 Previews:**\n{screenshots_md if screenshots_md else '*No visual previews captured.*'}
"""
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id} Implementation", pr_body)
        print(f"✨ ASYNC MISSION COMPLETE! PR: {pr_url}")
        
    except Exception as e:
        print(f"🔥 FATAL ERROR IN BACKGROUND AGENT WORKER: {str(e)}")