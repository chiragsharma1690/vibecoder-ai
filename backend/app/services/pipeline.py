import os
import json
from jira import JIRA

from app.schemas.models import ExecuteRequest
from app.core.workspace import WorkspaceManager
from app.core.config import MAX_CI_ATTEMPTS
from app.services.executor import run_shell_command
from app.agents.developer import run_developer_agent
from app.agents.reviewer import run_reviewer_agent
from app.agents.devops import run_devops_agent
from app.agents.architect import generate_architect_plan


def _build_current_files_context(workspace: WorkspaceManager, saved_files: list) -> str:
    """Provides the AI with its current code state without using confusing delimiters."""
    if not saved_files: return ""
    context = "\n\n### YOUR CURRENT IMPLEMENTATION (MODIFY THESE FILES) ###\n"
    for f_path in saved_files:
        full_path = os.path.join(workspace.repo_path, f_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                context += f"\nFILE: {f_path}\n```\n{f.read()}\n```\n"
    return context

def run_multi_agent_loop(request: ExecuteRequest, session: dict, workspace: WorkspaceManager, ci_feedback: str = ""):
    """The Inner Loop: Developer writes code -> Local Reviewer checks it."""
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(request.ticket_id)
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    
    print("\n⚙️ --- PRE-FLIGHT SETUP ---")
    setup_logs = ""
    commands = request.plan.get("commands_to_run", [])
    
    if isinstance(commands, str):
        commands = [commands]
        
    # The LLM sometimes combines commands with '&&'. 
    # Let's split them so we can run them independently in our Python loop.
    flat_commands = []
    for cmd_group in commands:
        for single_cmd in cmd_group.split("&&"):
            if single_cmd.strip():
                flat_commands.append(single_cmd.strip())
                
    # Track the current directory so `cd` commands persist across separate subprocess calls
    current_cwd = workspace.repo_path
    
    for cmd in flat_commands:
        # Handle 'cd' commands manually to persist state
        if cmd.startswith("cd "):
            new_dir = cmd[3:].strip()
            current_cwd = os.path.abspath(os.path.join(current_cwd, new_dir))
            setup_logs += f"\n$ {cmd}\n(Changed directory to {new_dir})\n"
            print(f"📁 Changed execution directory to {new_dir}")
            continue
            
        print(f"🚀 Executing Architect Command: {cmd}")
        success, output = run_shell_command(cmd, current_cwd, timeout=300)
        
        setup_logs += f"\n$ {cmd}\n{output}\n"
        
        if success:
            print(f"✅ Command succeeded: {cmd[:50]}...")
        else:
            # ---> THE FIX: We log the failure but DO NOT break the loop! <---
            print(f"⚠️ Command failed (Skipping to next): {cmd[:50]}...\nLogs: {output[:200]}...")

    base_developer_prompt = f"""
    You are the Lead Developer Agent. Implement this approved plan.
    
    JIRA TICKET:\n{jira_context}
    APPROVED PLAN:\n{json.dumps(request.plan, indent=2)}
    
    PRE-FLIGHT LOGS:\n{setup_logs if setup_logs else "No setup commands ran."}
    
    CURRENT REPOSITORY STRUCTURE:\n{workspace.get_repo_tree()}
    {ci_feedback}
    
    CRITICAL INSTRUCTIONS (ANTI-LAZINESS PROTOCOL): 
    1. Look at the `new_files` and `files_to_modify` lists in the APPROVED PLAN. You MUST generate the complete, fully implemented code for EVERY SINGLE FILE listed. 
    2. If the plan asks for 6 files, your JSON array MUST contain exactly 6 objects. Do not skip any files.
    3. NO PLACEHOLDERS: Do not leave comments like "// implement logic here" or "// rest of the code". Write the actual, working code.
    4. DO NOT output bash commands, terminal scripts, or explanations.
    5. You MUST output your response as a strict JSON array.
    
    EXACT SCHEMA REQUIRED:
    [
      {{
        "filepath": "path/file.ext",
        "content": "raw source code here..."
      }}
    ]
    """
    
    developer_prompt = base_developer_prompt
    saved_files = []
    pipeline_logs = []

    for attempt in range(1, 4):
        print(f"\n🔄 --- LOCAL INNER LOOP ATTEMPT {attempt}/3 ---")
        try:
            run_developer_agent(developer_prompt, workspace.repo_path, saved_files)
            if not saved_files: raise ValueError("Developer Agent failed to generate files.")
        except ValueError as e:
            print(f"⚠️ Developer Phase Failed: {e}")
            pipeline_logs.append(f"Developer Error: {str(e)}")
            developer_prompt = base_developer_prompt + f"\n\n🚨 URGENT JSON ERROR: Your previous attempt failed to parse ({e}). Ensure strict JSON compliance."
            continue

        diff_text = "".join([f"\n--- FILE: {d['file']} ---\nNEW CODE:\n{d['new_content']}\n" for d in workspace.get_file_diffs(saved_files)])
        is_approved, review_text = run_reviewer_agent(request.ticket_id, jira_context, workspace.get_repo_tree(), diff_text)
        pipeline_logs.append(f"Local Code Review: {review_text}")

        if not is_approved:
            print("⚠️ Local Reviewer caught issues! Bouncing back to Developer...")
            current_code = _build_current_files_context(workspace, saved_files)
            developer_prompt = base_developer_prompt + current_code + f"\n\n🚨 LOCAL CODE REVIEW REJECTED:\n{review_text}\n\nFIX THE ISSUES AND RETURN THE UPDATED FILES AS A JSON ARRAY."
            continue 
            
        print("✅ Local Reviewer approved the code! Ready for remote push.")
        break

    return saved_files, pipeline_logs

def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    """The Outer Loop: Dev/Review Loop -> Push -> GitHub Actions CI -> Self-Heal."""
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        run_devops_agent(workspace.get_repo_tree(), workspace.repo_path)

        ci_feedback = ""
        ci_success = True
        
        for ci_attempt in range(1, MAX_CI_ATTEMPTS + 1):
            print(f"\n🚀 === REMOTE CI PIPELINE ATTEMPT {ci_attempt}/{MAX_CI_ATTEMPTS} ===")
            
            saved_files, _ = run_multi_agent_loop(request, session, workspace, ci_feedback=ci_feedback)
            
            workspace.ensure_gitignore()
            workspace.run_git_command("add", ".")
            if workspace.run_git_command("status", "--porcelain", check=False).stdout.strip():
                workspace.run_git_command("commit", "-m", f"VibeCoder Attempt {ci_attempt} for {request.ticket_id}")
                workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
            else:
                print("⏭️ No code changes detected. Pushing existing branch state.")
                workspace.run_git_command("push", "--set-upstream", "origin", branch_name, check=False)
                
            ci_result = workspace.wait_for_ci_and_get_logs(branch_name)
            if ci_result["success"]:
                print("🎉 Remote CI passed!")
                ci_success = True
                break
            else:
                print("❌ Remote CI failed! Gathering logs for self-healing...")
                ci_success = False
                if ci_attempt < MAX_CI_ATTEMPTS:
                    current_code = _build_current_files_context(workspace, saved_files)
                    ci_feedback = f"\n\n🚨 REMOTE CI FAILED:\n{ci_result['logs']}\n{current_code}\n\nFIX THE BUILD FAILURES AND RETURN THE UPDATED FILES AS A JSON ARRAY."

        pr_body = f"### 🤖 VibeCoder Implementation\nResolves: **{request.ticket_id}**\nLocal Review Passed: ✅\nCI Passed: {'✅' if ci_success else '❌'}"
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id}", pr_body)
        print(f"✨ FEATURE PR OPENED: {pr_url}")
        
    except Exception as e:
        print(f"🔥 FATAL ERROR: {str(e)}")

def slack_autopilot_worker(ticket_id: str, description: str, session: dict, workspace: WorkspaceManager):
    try:
        jira_context = f"Description: {description}"
        repo_tree = workspace.get_repo_tree()
        
        plan_data = generate_architect_plan(ticket_id, jira_context, repo_tree)
        execute_request = ExecuteRequest(ticket_id=ticket_id, plan=plan_data, async_mode=True)
        
        background_agent_worker(execute_request, session, workspace)
        
    except Exception as e:
        print(f"🔥 Slack Autopilot Error: {str(e)}")