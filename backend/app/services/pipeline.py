import os
import json
from jira import JIRA

from app.schemas.models import ExecuteRequest
from app.core.workspace import WorkspaceManager
from app.core.config import MAX_CI_ATTEMPTS
from app.services.executor import run_shell_command
from app.agents.developer import run_developer_agent
from app.agents.devops import run_devops_agent

def _build_current_files_context(workspace: WorkspaceManager, saved_files: list) -> str:
    if not saved_files: return ""
    context = "\n\n### YOUR CURRENT IMPLEMENTATION (MODIFY THESE FILES) ###\n"
    for f_path in saved_files:
        full_path = os.path.join(workspace.repo_path, f_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                context += f"---FILE: {f_path}---\n{f.read()}\n---END---\n"
    return context

def run_developer_phase(request: ExecuteRequest, session: dict, workspace: WorkspaceManager, ci_feedback: str = ""):
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(request.ticket_id)
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    
    print("\n⚙️ --- PRE-FLIGHT SETUP ---")
    setup_logs = ""
    for cmd in request.plan.get("commands_to_run", []): 
        if cmd.strip(): 
            print(f"🚀 Executing Architect Command: {cmd}")
            success, output = run_shell_command(cmd, workspace.repo_path, timeout=300)
            setup_logs += f"\n$ {cmd}\n{output}\n"

    developer_prompt = f"""
    You are the Lead Developer Agent. Implement this approved plan.
    JIRA TICKET:\n{jira_context}
    APPROVED PLAN:\n{json.dumps(request.plan, indent=2)}
    PRE-FLIGHT LOGS:\n{setup_logs if setup_logs else "No setup commands ran."}
    CURRENT REPOSITORY STRUCTURE:\n{workspace.get_repo_tree()}
    {ci_feedback}
    
    CRITICAL INSTRUCTIONS: 
    1. Generate complete code for EVERY SINGLE FILE.
    2. Do NOT wrap the code in markdown code blocks.
    EXAMPLE OUTPUT FORMAT:
    ---FILE: path/file.ext---
    // raw code
    ---END---
    """
    
    saved_files = []
    try:
        run_developer_agent(developer_prompt, workspace.repo_path, saved_files)
        if not saved_files: raise ValueError("Developer Agent failed to generate files.")
    except ValueError as e:
        print(f"⚠️ Developer Phase Failed: {e}")
        
    return saved_files

def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        # 0. DevOps Phase (Ensures GitHub Actions is setup)
        run_devops_agent(workspace.get_repo_tree(), workspace.repo_path)

        ci_feedback = ""
        ci_success = True
        
        for ci_attempt in range(1, MAX_CI_ATTEMPTS + 1):
            print(f"\n🚀 === CI PIPELINE ATTEMPT {ci_attempt}/{MAX_CI_ATTEMPTS} ===")
            
            # 1. Developer generates code based on plan (and optional CI feedback)
            saved_files = run_developer_phase(request, session, workspace, ci_feedback=ci_feedback)
            
            # 2. Push to GitHub to trigger remote pipeline
            workspace.ensure_gitignore()
            workspace.run_git_command("add", ".")
            if workspace.run_git_command("status", "--porcelain", check=False).stdout.strip():
                workspace.run_git_command("commit", "-m", f"VibeCoder Attempt {ci_attempt} for {request.ticket_id}")
                workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
            else:
                print("⏭️ No code changes detected. Pushing existing branch state.")
                workspace.run_git_command("push", "--set-upstream", "origin", branch_name, check=False)
                
            # 3. Wait for Remote CI Feedback
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
                    ci_feedback = f"\n\n🚨 REMOTE CI FAILED:\n{ci_result['logs']}\n{current_code}"

        # 4. Open PR (This wakes up your standalone Reviewer and Tester bots via GitHub Webhooks!)
        pr_body = f"### 🤖 VibeCoder Implementation\nResolves: **{request.ticket_id}**\nCI Passed: {'✅' if ci_success else '❌'}"
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id}", pr_body)
        print(f"✨ FEATURE PR OPENED: {pr_url}")
        
    except Exception as e:
        print(f"🔥 FATAL ERROR: {str(e)}")