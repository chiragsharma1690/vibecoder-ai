from fastapi import APIRouter, HTTPException, Depends, Response
from jira import JIRA

from app.schemas.models import ConnectRequest, SetBranchRequest
from app.core.workspace import WorkspaceManager
from app.core.dependencies import get_current_session, create_session_token

router = APIRouter(prefix="/api", tags=["Workspace"])

@router.post("/connect")
async def connect_workspace(request: ConnectRequest, response: Response):
    """Authenticates the user and sets the secure JWT session cookie."""
    try:
        jira_client = JIRA(server=request.jira_url, basic_auth=(request.jira_user, request.jira_token))
        jira_client.myself()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Jira Authentication Failed: {str(e)}")

    workspace = WorkspaceManager(request.repo_url, request.github_token)
    if not workspace.verify_access():
        raise HTTPException(status_code=401, detail="GitHub Authentication Failed.")

    repo_path = workspace.setup_workspace()
    
    # Generate and set the signed JWT session cookie
    session_data = {
        "repo_url": request.repo_url,
        "github_token": request.github_token,
        "jira_url": request.jira_url,
        "jira_user": request.jira_user,
        "jira_token": request.jira_token,
        "jira_project_key": getattr(request, 'jira_project_key', '') 
    }
    
    token = create_session_token(session_data)
    
    response.set_cookie(
        key="vibecoder_session", 
        value=token, 
        httponly=True, 
        samesite="lax"
    )

    return {"status": "success", "workspace_path": repo_path, "branches": workspace.get_available_branches()}

@router.post("/set-branch")
async def set_base_branch(request: SetBranchRequest, session: dict = Depends(get_current_session)):
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    workspace.checkout_base_branch(request.branch_name)
    return {"status": "success"}