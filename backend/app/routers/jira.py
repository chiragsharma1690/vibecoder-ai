from fastapi import APIRouter, HTTPException, Depends
from jira import JIRA

from app.schemas.models import CreateTicketRequest
from app.core.dependencies import get_current_session

router = APIRouter(prefix="/api/jira", tags=["Jira"])

@router.post("/create")
async def create_jira_ticket(request: CreateTicketRequest, session: dict = Depends(get_current_session)):
    project_key = session.get("jira_project_key")
    if not project_key:
        raise HTTPException(status_code=400, detail="Jira Project Key is missing from session.")

    try:
        jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
        issue_dict = {
            'project': {'key': project_key},
            'summary': request.summary,
            'description': request.description,
            'issuetype': {'name': 'Task'},
        }
        new_issue = jira_client.create_issue(fields=issue_dict)
        return {"status": "success", "ticket_id": new_issue.key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Jira ticket: {str(e)}")