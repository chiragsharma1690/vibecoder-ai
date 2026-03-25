import os
import json
from jira import JIRA

from schemas import ExecuteRequest
from workspace import WorkspaceManager
from qa_tools import run_shell_command, run_qa_tests, capture_coverage_screenshot
from agents import run_developer_agent, generate_qa_command, run_reviewer_agent


def _build_current_files_context(workspace: WorkspaceManager, saved_files: list) -> str:
    """Helper: Reads the currently generated files to feed back to the LLM for self-healing."""
    if not saved_files: return ""
    
    context = "\n\n### YOUR CURRENT IMPLEMENTATION (MODIFY THESE FILES) ###\n"
    for f_path in saved_files:
        full_path = os.path.join(workspace.repo_path, f_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            context += f"---FILE: {f_path}---\n{content}\n---END---\n"
    return context


def run_multi_agent_loop(request: ExecuteRequest, session: dict, workspace: WorkspaceManager, 
                         enable_qa: bool = True, enable_code_review: bool = True):
    """Orchestrates the Developer, QA, and Reviewer."""
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(request.ticket_id)
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    
    base_developer_prompt = f"""
    You are the Lead Developer Agent. Implement this approved plan.
    JIRA TICKET:\n{jira_context}\nAPPROVED PLAN:\n{json.dumps(request.plan, indent=2)}
    CURRENT REPOSITORY STRUCTURE:\n{workspace.get_repo_tree()}
    
    CRITICAL INSTRUCTIONS: 
    Write the implementation code. You MUST wrap EVERY file you create or modify strictly in the following format. 
    DO NOT wrap the code in markdown code blocks (e.g., ```javascript or ```yaml). 
    DO NOT include conversational text.
    
    EXAMPLE OUTPUT FORMAT:
    ---FILE: path/to/the/file.ext---
    // your raw functional code goes here
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
        try:
            run_developer_agent(developer_prompt, workspace.repo_path, saved_files)
            if not saved_files: raise ValueError("Developer Agent failed to generate files.")
        except ValueError as e:
            print(f"⚠️ Developer Phase Failed: {e}")
            qa_logs.append(f"Developer Error: {str(e)}")
            developer_prompt = base_developer_prompt + f"\n\n🚨 URGENT: Previous attempt failed ({e}). Please provide a concise, optimized response."
            continue 

        if attempt == 1:
            for cmd in request.plan.get("commands_to_run", []): 
                if cmd.strip(): run_shell_command(cmd, workspace.repo_path)

        # 2. QA PHASE
        if enable_qa:
            try:
                test_cmd = generate_qa_command(saved_files, workspace.get_repo_tree(), workspace.repo_path, last_qa_error)
                qa_success, qa_output = run_qa_tests(test_cmd, workspace.repo_path)
                qa_logs.append(f"QA Execution: {qa_output}")

                if not qa_success:
                    print(f"❌ QA Check Failed. Self-healing...")
                    last_qa_error = qa_output
                    truncated_qa_output = qa_output[-4000:] if len(qa_output) > 4000 else qa_output
                    
                    # 🚨 FIX: Feed the current code context back to the LLM so it knows WHAT to fix
                    current_code = _build_current_files_context(workspace, saved_files)
                    
                    developer_prompt = base_developer_prompt + current_code + f"\n\n🚨 URGENT - TEST EXECUTION FAILED:\n{truncated_qa_output}\nFix the code above to pass with >80% coverage. Output the corrected files using the EXACT SAME FILE PATHS. Do not invent new file names."
                    continue 
                
                print("🎉 QA Agent approved the tests!")
                last_qa_error = ""
            except ValueError as e:
                print(f"⚠️ QA Phase Failed: {e}")
                qa_logs.append(f"QA Agent Error: {str(e)}")
                continue 
        else:
            qa_passed = True

        # 3. REVIEWER PHASE
        if enable_code_review:
            try:
                diff_text = "".join([f"\n--- FILE: {d['file']} ---\nNEW CODE:\n{d['new_content']}\n" for d in workspace.get_file_diffs(saved_files)])
                is_approved, review_text = run_reviewer_agent(request.ticket_id, diff_text)
                qa_logs.append(f"Code Review: {review_text}")

                if not is_approved:
                    print("⚠️ Senior Reviewer requested changes. Self-healing...")
                    
                    # 🚨 FIX: Feed the current code context back to the LLM so it knows WHAT to fix
                    current_code = _build_current_files_context(workspace, saved_files)
                    
                    developer_prompt = base_developer_prompt + current_code + f"\n\n🚨 URGENT - CODE REVIEWER REJECTED YOUR CODE:\nREVIEWER FEEDBACK:\n{review_text}\nFix the issues and output the corrected files using the EXACT SAME FILE PATHS."
                    continue 
                
                print("✅ Senior Reviewer approved the code!")
            except ValueError as e:
                print(f"⚠️ Reviewer Phase Failed: {e}")
                qa_logs.append(f"Reviewer Error: {str(e)}")
                continue

        qa_passed = True
        break

    return saved_files, qa_passed, qa_logs

def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    """The asynchronous PR generation task."""
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        saved_files, qa_passed, qa_logs = run_multi_agent_loop(request, session, workspace, enable_qa=True, enable_code_review=True)

        workspace.ensure_gitignore()

        coverage_img_path = None
        cov_path = os.path.join(workspace.repo_path, ".agent", "coverage.txt")
        if os.path.exists(cov_path):
            with open(cov_path, "r", encoding="utf-8") as f:
                cov_text = f.read()[-2000:] 
            coverage_img_path = capture_coverage_screenshot(workspace.repo_path, cov_text)

        workspace.run_git_command("add", ".")
        if coverage_img_path:
            workspace.run_git_command("add", "-f", coverage_img_path)
        
        status_check = workspace.run_git_command("status", "--porcelain", check=False)
        
        if status_check.stdout.strip():
            workspace.run_git_command("commit", "-m", f"Auto-implemented {request.ticket_id}")
            workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
        else:
            print("⏭️ No code changes detected by Git. Pushing existing branch state.")
            workspace.run_git_command("push", "--set-upstream", "origin", branch_name, check=False)
            
        owner_repo = workspace.repo_url.replace("https://github.com/", "").replace(".git", "")
        
        pr_body = f"""### 🤖 VibeCoder AI Implementation
Resolves Jira Ticket: **{request.ticket_id}**

**Details:**
* Strategy: {request.plan.get('strategy', 'N/A')}
* Pipeline Passed: {'Yes ✅' if qa_passed else 'Failed / Skipped ⚠️'} 
"""
        
        if coverage_img_path:
            raw_img_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch_name}/{coverage_img_path}"
            pr_body += f"\n**📊 Coverage Report:**\n![Coverage]({raw_img_url})\n"
        
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id} Implementation", pr_body)
        print(f"✨ ASYNC MISSION COMPLETE! PR: {pr_url}")
        
    except Exception as e:
        print(f"🔥 FATAL ERROR IN BACKGROUND AGENT WORKER: {str(e)}")