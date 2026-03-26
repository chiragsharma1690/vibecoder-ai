import os
import json
from jira import JIRA

from schemas import ExecuteRequest
from workspace import WorkspaceManager
from qa_tools import run_shell_command, run_qa_tests, capture_coverage_screenshot
from agents import run_developer_agent, generate_qa_command, run_reviewer_agent

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

def run_multi_agent_loop(request: ExecuteRequest, session: dict, workspace: WorkspaceManager, 
                         enable_qa: bool = False, enable_code_review: bool = True):
    """
    The Core Orchestrator: Chains together the Developer, QA, and Reviewer agents in a robust 
    feedback loop. Supports self-healing up to `max_attempts`.
    """
    # Fetch JIRA contextual data
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(request.ticket_id)
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    
    # ----------------------------------------------------
    # PRE-FLIGHT PHASE: Run setup commands before coding
    # ----------------------------------------------------
    print("\n⚙️ --- PRE-FLIGHT SETUP ---")
    setup_commands = request.plan.get("commands_to_run", [])
    setup_logs = ""
    
    for cmd in setup_commands: 
        if cmd.strip(): 
            print(f"🚀 Executing Architect Command: {cmd}")
            success, output = run_shell_command(cmd, workspace.repo_path, timeout=300)
            setup_logs += f"\n$ {cmd}\n{output}\n"

    # Compile the strict instruction set for the Developer
    base_developer_prompt = f"""
    You are the Lead Developer Agent. Implement this approved plan.
    JIRA TICKET:\n{jira_context}
    
    APPROVED PLAN:\n{json.dumps(request.plan, indent=2)}
    
    PRE-FLIGHT COMMAND LOGS (Review these to see what was just installed/scaffolded):
    {setup_logs if setup_logs else "No setup commands ran."}
    
    CURRENT REPOSITORY STRUCTURE:\n{workspace.get_repo_tree()}
    
    CRITICAL INSTRUCTIONS: 
    1. ANTI-LAZINESS: You MUST generate the complete, fully-functioning code for EVERY SINGLE FILE listed in the plan's `new_files` and `files_to_modify` arrays. Do not skip any files.
    2. Do NOT leave TODOs or placeholders. Write production-ready code.
    3. You MUST wrap EVERY file you create or modify strictly in the following format. 
    4. DO NOT wrap the code in markdown code blocks (e.g., ```javascript or ```yaml). 
    
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

    # ----------------------------------------------------
    # EXECUTION LOOP: Developer -> QA -> Reviewer
    # ----------------------------------------------------
    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 --- PIPELINE ATTEMPT {attempt}/{max_attempts} ---")
        
        # --- 1. DEVELOPER PHASE ---
        try:
            run_developer_agent(developer_prompt, workspace.repo_path, saved_files)
            if not saved_files: raise ValueError("Developer Agent failed to generate files.")
        except ValueError as e:
            print(f"⚠️ Developer Phase Failed: {e}")
            qa_logs.append(f"Developer Error: {str(e)}")
            # Append error to base prompt to enforce context retention
            developer_prompt = base_developer_prompt + f"\n\n🚨 URGENT: Previous attempt failed ({e}). Please provide a concise, optimized response."
            continue

        # --- 2. QA PHASE ---
        if enable_qa:
            try:
                # Let QA dynamically generate test commands based on the updated repo state
                test_cmd = generate_qa_command(saved_files, workspace.get_repo_tree(), workspace.repo_path, last_qa_error)
                qa_success, qa_output = run_qa_tests(test_cmd, workspace.repo_path)
                qa_logs.append(f"QA Execution: {qa_output}")

                if not qa_success:
                    print(f"❌ QA Check Failed. Self-healing...")
                    last_qa_error = qa_output
                    # Truncate terminal logs to protect token limits
                    truncated_qa_output = qa_output[-4000:] if len(qa_output) > 4000 else qa_output
                    
                    # Feed current code back to developer for in-place patching
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

        # --- 3. REVIEWER PHASE ---
        if enable_code_review:
            try:
                # Concatenate diffs to send to the Reviewer
                diff_text = "".join([f"\n--- FILE: {d['file']} ---\nNEW CODE:\n{d['new_content']}\n" for d in workspace.get_file_diffs(saved_files)])
                
                is_approved, review_text = run_reviewer_agent(request.ticket_id, jira_context, diff_text)
                qa_logs.append(f"Code Review: {review_text}")

                if not is_approved:
                    print("⚠️ Senior Reviewer requested changes. Self-healing...")
                    current_code = _build_current_files_context(workspace, saved_files)
                    
                    # Bounce back to Developer with Reviewer's feedback
                    developer_prompt = base_developer_prompt + current_code + f"\n\n🚨 URGENT - CODE REVIEWER REJECTED YOUR CODE:\nREVIEWER FEEDBACK:\n{review_text}\nFix the issues and output the corrected files using the EXACT SAME FILE PATHS."
                    continue 
                
                print("✅ Senior Reviewer approved the code and verified ticket scope!")
            except ValueError as e:
                print(f"⚠️ Reviewer Phase Failed: {e}")
                qa_logs.append(f"Reviewer Error: {str(e)}")
                continue

        # If it reaches here without triggering a 'continue', the pipeline was a complete success!
        qa_passed = True
        break

    return saved_files, qa_passed, qa_logs

def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    """
    The asynchronous background task used when 'Async Mode' is toggled.
    Runs the pipeline, stages files, forcefully adds QA reports, commits, and opens a Pull Request.
    """
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        # Execute the primary loop
        saved_files, qa_passed, qa_logs = run_multi_agent_loop(request, session, workspace, enable_qa=False, enable_code_review=True)

        workspace.ensure_gitignore()
        
        # Capture and append visual coverage proof, if exists
        coverage_img_path = None
        cov_path = os.path.join(workspace.repo_path, ".agent", "coverage.txt")
        if os.path.exists(cov_path):
            with open(cov_path, "r", encoding="utf-8") as f:
                cov_text = f.read()[-2000:] 
            coverage_img_path = capture_coverage_screenshot(workspace.repo_path, cov_text)

        # ----------------------------------------------------
        # GIT OPERATIONS & PULL REQUEST
        # ----------------------------------------------------
        workspace.run_git_command("add", ".")
        # Force add the image just in case .github is ignored in the user's config
        if coverage_img_path:
            workspace.run_git_command("add", "-f", coverage_img_path)
        
        status_check = workspace.run_git_command("status", "--porcelain", check=False)
        
        # Only commit if changes actually occurred to prevent CalledProcessError crashes
        if status_check.stdout.strip():
            workspace.run_git_command("commit", "-m", f"Auto-implemented {request.ticket_id}")
            workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
        else:
            print("⏭️ No code changes detected by Git. Pushing existing branch state.")
            workspace.run_git_command("push", "--set-upstream", "origin", branch_name, check=False)
            
        owner_repo = workspace.repo_url.replace("https://github.com/", "").replace(".git", "")
        
        # Compile the markdown PR Body
        pr_body = f"""### 🤖 VibeCoder AI Implementation
Resolves Jira Ticket: **{request.ticket_id}**

**Details:**
* Strategy: {request.plan.get('strategy', 'N/A')}
* Pipeline Passed: {'Yes ✅' if qa_passed else 'Failed / Skipped ⚠️'} 
"""
        
        # Embed the raw GitHub image link dynamically
        if coverage_img_path:
            raw_img_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch_name}/{coverage_img_path}"
            pr_body += f"\n**📊 Coverage Report:**\n![Coverage]({raw_img_url})\n"
        
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id} Implementation", pr_body)
        print(f"✨ ASYNC MISSION COMPLETE! PR: {pr_url}")
        
    except Exception as e:
        print(f"🔥 FATAL ERROR IN BACKGROUND AGENT WORKER: {str(e)}")