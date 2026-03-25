from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from jira import JIRA

from schemas import ConnectRequest, PlanRequest, ExecuteRequest, PushRequest, SetBranchRequest
from session import save_session, load_session
from workspace import WorkspaceManager
from agents import generate_architect_plan
from pipeline import run_multi_agent_loop, background_agent_worker

# Initialize the app
app = FastAPI(title="VibeCoder AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "[http://127.0.0.1:5173](http://127.0.0.1:5173)"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    return {"status": "active", "message": "VibeCoder Backend is alive."}

@app.post("/api/connect")
async def connect_workspace(request: ConnectRequest):
    # Validate Jira
    try:
        jira_client = JIRA(server=request.jira_url, basic_auth=(request.jira_user, request.jira_token))
        jira_client.myself()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Jira Authentication Failed. Error: {str(e)}")

    # Setup Workspace
    workspace = WorkspaceManager(request.repo_url, request.github_token)
    if not workspace.verify_access():
        raise HTTPException(status_code=401, detail="GitHub Authentication Failed.")

    try: 
        repo_path = workspace.setup_workspace()
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Failed to clone repository: {str(e)}")
    
    # Save active state
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
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    plan_data = generate_architect_plan(request, session, workspace)
    
    return {
        "status": "success", 
        "ticket_id": request.ticket_id, 
        "plan": plan_data, 
        "is_revision": bool(request.feedback)
    }

@app.post("/api/chat/execute")
async def execute_plan(request: ExecuteRequest, background_tasks: BackgroundTasks):
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])

    if request.async_mode:
        background_tasks.add_task(background_agent_worker, request, session, workspace)
        return {
            "status": "async", 
            "message": f"Agent dispatched. A Pull Request for {request.ticket_id} will be generated."
        }
    else:
        # Sync Mode
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
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    # We reconstruct the branch name using UUID logic if needed, 
    # but strictly following the PR branch name format requested earlier.
    # Note: In synchronous flow, you might need to read the current branch name via git
    current_branch_cmd = workspace.run_git_command("branch", "--show-current")
    branch_name = current_branch_cmd.stdout.strip()
    
    workspace.run_git_command("add", ".")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)