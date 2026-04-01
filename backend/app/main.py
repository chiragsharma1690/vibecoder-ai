from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from jira import JIRA

from app.schemas.models import ConnectRequest, PlanRequest, ExecuteRequest, PushRequest, SetBranchRequest
from app.core.session import save_session, load_session
from app.core.workspace import WorkspaceManager
from app.agents.architect import generate_architect_plan
from app.services.pipeline import background_agent_worker, run_multi_agent_loop
from app.routers import webhooks

app = FastAPI(title="VibeCoder Core Runtime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
)

app.include_router(webhooks.router)

@app.get("/")
async def health_check():
    return {"status": "active", "message": "VibeCoder Backend is alive."}

@app.post("/api/connect")
async def connect_workspace(request: ConnectRequest):
    try:
        jira_client = JIRA(server=request.jira_url, basic_auth=(request.jira_user, request.jira_token))
        jira_client.myself()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Jira Authentication Failed: {str(e)}")

    workspace = WorkspaceManager(request.repo_url, request.github_token)
    if not workspace.verify_access():
        raise HTTPException(status_code=401, detail="GitHub Authentication Failed.")

    repo_path = workspace.setup_workspace()
    save_session({
        "github_token": request.github_token, "jira_url": request.jira_url,
        "jira_user": request.jira_user, "jira_token": request.jira_token,
        "repo_url": request.repo_url, "repo_name": workspace.repo_name
    })

    return {"status": "success", "workspace_path": repo_path, "branches": workspace.get_available_branches()}

@app.post("/api/set-branch")
async def set_base_branch(request: SetBranchRequest):
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    workspace.checkout_base_branch(request.branch_name)
    session["base_branch"] = request.branch_name
    save_session(session)
    return {"status": "success"}

@app.post("/api/chat/plan")
async def generate_plan(request: PlanRequest):
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(request.ticket_id)
    
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    plan_data = generate_architect_plan(request.ticket_id, jira_context, workspace.get_repo_tree(), request.feedback, request.previous_plan)
    
    return {"status": "success", "ticket_id": request.ticket_id, "plan": plan_data, "is_revision": bool(request.feedback)}

@app.post("/api/chat/execute")
async def execute_plan(request: ExecuteRequest, background_tasks: BackgroundTasks):
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])

    if request.async_mode:
        background_tasks.add_task(background_agent_worker, request, session, workspace)
        return {"status": "async", "message": f"Agent dispatched. PR for {request.ticket_id} will be generated."}
    else:
        # Sync mode fallback if needed for UI debugging
        base_branch = session.get("base_branch", "main")
        workspace.setup_branch(request.ticket_id, base_branch)
        try:
            saved_files, pipeline_logs = run_multi_agent_loop(request, session, workspace)
            return {"status": "success", "files_created": saved_files, "file_diffs": workspace.get_file_diffs(saved_files)}
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/push")
async def push_code(request: PushRequest):
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    branch_name = workspace.run_git_command("branch", "--show-current").stdout.strip()
    workspace.run_git_command("add", ".")
    if not workspace.run_git_command("status", "--porcelain").stdout.strip():
        return {"status": "skipped", "message": "Git reports no changes."}
        
    if workspace.run_git_command("commit", "-m", f"Auto-implementation of {request.ticket_id}").returncode != 0:
        raise HTTPException(status_code=500, detail="Failed to commit code.")
        
    if workspace.run_git_command("push", "--set-upstream", "origin", branch_name).returncode != 0:
        raise HTTPException(status_code=500, detail="Failed to push to GitHub.")

    return {"status": "success", "branch": branch_name}