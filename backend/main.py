from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from jira import JIRA

from schemas import ConnectRequest, PlanRequest, ExecuteRequest, PushRequest, SetBranchRequest
from session import save_session, load_session
from workspace import WorkspaceManager
from agents import generate_architect_plan
from pipeline import run_multi_agent_loop, background_agent_worker, async_pr_reviewer_worker, async_test_generation_worker

# Initialize the FastAPI App
app = FastAPI(title="VibeCoder AI API")

# Configure CORS to allow the React frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "active", "message": "VibeCoder Backend is alive."}

@app.post("/api/connect")
async def connect_workspace(request: ConnectRequest):
    """
    Validates external credentials, initializes the workspace manager, 
    clones the repository, and saves the session data locally.
    """
    # Validate Jira
    try:
        jira_client = JIRA(server=request.jira_url, basic_auth=(request.jira_user, request.jira_token))
        jira_client.myself()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Jira Authentication Failed. Error: {str(e)}")

    # Validate GitHub and Setup Workspace
    workspace = WorkspaceManager(request.repo_url, request.github_token)
    if not workspace.verify_access():
        raise HTTPException(status_code=401, detail="GitHub Authentication Failed.")

    try: 
        repo_path = workspace.setup_workspace()
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Failed to clone repository: {str(e)}")
    
    # Persist the connection config across API calls
    save_session({
        "github_token": request.github_token, 
        "jira_url": request.jira_url,
        "jira_user": request.jira_user, 
        "jira_token": request.jira_token,
        "repo_url": request.repo_url, 
        "repo_name": workspace.repo_name
    })

    return {
        "status": "success", 
        "message": f"Successfully connected to {workspace.repo_name}.",
        "workspace_path": repo_path,
        "branches": workspace.get_available_branches()
    }

@app.post("/api/set-branch")
async def set_base_branch(request: SetBranchRequest):
    """Allows the user to select the foundational Git branch for operations."""
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    try:
        workspace.checkout_base_branch(request.branch_name)
        session["base_branch"] = request.branch_name
        save_session(session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to checkout branch: {str(e)}")

    return {"status": "success", "message": f"Switched to base branch: {request.branch_name}"}

@app.post("/api/chat/plan")
async def generate_plan(request: PlanRequest):
    """
    Invokes the Architect Agent to map out the strategy, necessary file changes, 
    and pre-flight commands needed to resolve the provided Jira Ticket.
    """
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    try:
        jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
        issue = jira_client.issue(request.ticket_id)
        jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch Jira ticket {request.ticket_id}: {str(e)}")
    
    try:
        plan_data = generate_architect_plan(
            ticket_id=request.ticket_id,
            jira_context=jira_context,
            repo_tree=workspace.get_repo_tree(),
            feedback=request.feedback,
            previous_plan=request.previous_plan
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Architect Agent Failed: {str(e)}")
    
    return {
        "status": "success", 
        "ticket_id": request.ticket_id, 
        "plan": plan_data, 
        "is_revision": bool(request.feedback)
    }

@app.post("/api/chat/execute")
async def execute_plan(request: ExecuteRequest, background_tasks: BackgroundTasks):
    """
    Triggers the Multi-Agent coding pipeline. Routes execution to a background worker 
    if 'async_mode' is True; otherwise, runs synchronously and returns execution diffs to the UI.
    """
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])

    if request.async_mode:
        background_tasks.add_task(background_agent_worker, request, session, workspace)
        return {
            "status": "async", 
            "message": f"Agent dispatched. A Pull Request for {request.ticket_id} will be generated."
        }
    else:
        # Sync Mode: Blocks the API request until the pipeline finishes
        base_branch = session.get("base_branch", "main")
        workspace.setup_branch(request.ticket_id, base_branch)
        
        try:
            saved_files, qa_passed, qa_logs = run_multi_agent_loop(request, session, workspace)
            file_diffs = workspace.get_file_diffs(saved_files)

            return {
                "status": "success", 
                "message": f"Execution finished. QA Passed: {qa_passed}.",
                "files_created": saved_files, 
                "test_passed": qa_passed,
                "qa_logs": qa_logs, 
                "file_diffs": file_diffs
            }
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/push")
async def push_code(request: PushRequest):
    """Allows manual approval of synchronous mode changes, committing and pushing them to remote."""
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    # Retrieve the name of the feature branch we are currently resting on
    current_branch_cmd = workspace.run_git_command("branch", "--show-current")
    branch_name = current_branch_cmd.stdout.strip()
    
    workspace.run_git_command("add", ".")
    
    # Short-circuit if there are no real changes to push
    if not workspace.run_git_command("status", "--porcelain").stdout.strip():
        return {"status": "skipped", "message": "Git reports no changes."}
        
    if workspace.run_git_command("commit", "-m", f"Auto-implementation of {request.ticket_id}").returncode != 0:
        raise HTTPException(status_code=500, detail="Failed to commit code.")
        
    if workspace.run_git_command("push", "--set-upstream", "origin", branch_name).returncode != 0:
        raise HTTPException(status_code=500, detail="Failed to push to GitHub.")

    return {
        "status": "success", 
        "message": "Successfully pushed all changes to GitHub!", 
        "branch": branch_name
    }

@app.post("/api/webhooks/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Listens for GitHub Webhook events. 
    Triggers the Async PR Reviewer and the Async Test Engineer when a PR is opened.
    """
    payload = await request.json()
    event = request.headers.get("X-GitHub-Event")

    if event == "pull_request":
        action = payload.get("action")
        pr_info = payload.get("pull_request", {})
        branch_name = pr_info.get("head", {}).get("ref", "")
        
        # Guard: Prevent infinite loops! We don't want to review our own test branches
        if action in ["opened", "synchronize"] and not branch_name.endswith("-testing"):
            session = load_session()
            
            print(f"🔔 Webhook received! PR {action} on branch {branch_name}. Dispatching bots...")
            
            # 1. Dispatch the PR Review Bot (runs on new PRs and new commits)
            background_tasks.add_task(async_pr_reviewer_worker, payload, session)
            
            # 2. Dispatch the Test Engineer Bot (only on PR creation to avoid duplicate test branches)
            if action == "opened":
                background_tasks.add_task(async_test_generation_worker, payload, session)

    return {"status": "received"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)