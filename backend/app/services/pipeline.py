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

def _build_current_files_context(workspace: WorkspaceManager, saved_files: list) -> str:
    if not saved_files: return ""
    context = "\n\n### YOUR CURRENT IMPLEMENTATION (MODIFY THESE FILES) ###\n"
    for f_path in saved_files:
        full_path = os.path.join(workspace.repo_path, f_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                context += f"---FILE: {f_path}---\n{f.read()}\n---END---\n"
    return context

def run_multi_agent_loop(request: ExecuteRequest, session: dict, workspace: WorkspaceManager, ci_feedback: str = ""):
    """The Inner Loop: Developer writes code -> Local Reviewer checks it."""
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

    base_developer_prompt = f"""
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
    
    developer_prompt = base_developer_prompt
    saved_files = []
    pipeline_logs = []

    # LOCAL INNER LOOP (Max 3 bounces back and forth)
    for attempt in range(1, 4):
        print(f"\n🔄 --- LOCAL INNER LOOP ATTEMPT {attempt}/3 ---")
        try:
            run_developer_agent(developer_prompt, workspace.repo_path, saved_files)
            if not saved_files: raise ValueError("Developer Agent failed to generate files.")
        except ValueError as e:
            print(f"⚠️ Developer Phase Failed: {e}")
            pipeline_logs.append(f"Developer Error: {str(e)}")
            developer_prompt = base_developer_prompt + f"\n\n🚨 URGENT: Previous attempt failed ({e})."
            continue

        # FIRST LINE OF DEFENSE: Local Code Review
        diff_text = "".join([f"\n--- FILE: {d['file']} ---\nNEW CODE:\n{d['new_content']}\n" for d in workspace.get_file_diffs(saved_files)])
        is_approved, review_text = run_reviewer_agent(request.ticket_id, jira_context, workspace.get_repo_tree(), diff_text)
        pipeline_logs.append(f"Local Code Review: {review_text}")

        if not is_approved:
            print("⚠️ Local Reviewer caught issues! Bouncing back to Developer...")
            current_code = _build_current_files_context(workspace, saved_files)
            developer_prompt = base_developer_prompt + current_code + f"\n\n🚨 LOCAL CODE REVIEW REJECTED:\n{review_text}"
            continue 
            
        print("✅ Local Reviewer approved the code! Ready for remote push.")
        break

    return saved_files, pipeline_logs

def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    """The Outer Loop: Dev/Review Loop -> Push -> GitHub Actions CI -> Self-Heal."""
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        # 0. DevOps Phase (Ensures GitHub Actions is setup)
        run_devops_agent(workspace.get_repo_tree(), workspace.repo_path)

        ci_feedback = ""
        ci_success = True
        
        # REMOTE OUTER LOOP
        for ci_attempt in range(1, MAX_CI_ATTEMPTS + 1):
            print(f"\n🚀 === REMOTE CI PIPELINE ATTEMPT {ci_attempt}/{MAX_CI_ATTEMPTS} ===")
            
            # 1. Trigger the Local Inner Loop (Develop -> Local Review)
            saved_files, _ = run_multi_agent_loop(request, session, workspace, ci_feedback=ci_feedback)
            
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

        # 4. Open PR (This wakes up your standalone PR Bot and Tester Bot via GitHub Webhooks!)
        pr_body = f"### 🤖 VibeCoder Implementation\nResolves: **{request.ticket_id}**\nLocal Review Passed: ✅\nCI Passed: {'✅' if ci_success else '❌'}"
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id}", pr_body)
        print(f"✨ FEATURE PR OPENED: {pr_url}")
        
    except Exception as e:
        print(f"🔥 FATAL ERROR: {str(e)}")