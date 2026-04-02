from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from jira import JIRA

from app.schemas.models import PlanRequest, ExecuteRequest, PushRequest
from app.core.workspace import WorkspaceManager
from app.core.dependencies import get_current_session
from app.agents.architect import generate_architect_plan
from app.services.pipeline import background_agent_worker, run_multi_agent_loop

router = APIRouter(prefix="/api/chat", tags=["Agent Chat"])

@router.post("/plan")
async def generate_plan(request: PlanRequest, session: dict = Depends(get_current_session)):
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(request.ticket_id)
    
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    plan_data = generate_architect_plan(request.ticket_id, jira_context, workspace.get_repo_tree(), request.feedback, request.previous_plan)
    
    return {"status": "success", "ticket_id": request.ticket_id, "plan": plan_data, "is_revision": bool(request.feedback)}

@router.post("/execute")
async def execute_plan(request: ExecuteRequest, background_tasks: BackgroundTasks, session: dict = Depends(get_current_session)):
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])

    if request.async_mode:
        background_tasks.add_task(background_agent_worker, request, session, workspace)
        return {"status": "async", "message": f"Agent dispatched. PR for {request.ticket_id} will be generated."}
    else:
        base_branch = session.get("base_branch", "main")
        workspace.setup_branch(request.ticket_id, base_branch)
        try:
            saved_files, pipeline_logs = run_multi_agent_loop(request, session, workspace)
            return {"status": "success", "files_created": saved_files, "file_diffs": workspace.get_file_diffs(saved_files)}
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/push")
async def push_code(request: PushRequest, session: dict = Depends(get_current_session)):
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