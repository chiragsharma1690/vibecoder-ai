from fastapi import APIRouter, BackgroundTasks, Form, Depends, HTTPException
from jira import JIRA

from app.core.database import get_slack_user, save_slack_user
from app.core.dependencies import get_current_session
from app.schemas.models import LinkSlackRequest
from app.core.workspace import WorkspaceManager
from app.services.pipeline import slack_autopilot_worker

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

@router.post("/slack/link")
async def link_slack_account(request: LinkSlackRequest, session: dict = Depends(get_current_session)):
    try:
        save_slack_user(request.slack_user_id, session)
        return {"status": "success", "message": f"Successfully linked Slack ID {request.slack_user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/slack")
async def slack_webhook(
    background_tasks: BackgroundTasks,
    text: str = Form(...),         
    user_id: str = Form(...), 
    user_name: str = Form(...)     
):
    session_data = get_slack_user(user_id)
    if not session_data:
        return {
            "response_type": "ephemeral",
            "text": f"⚠️ Hello {user_name}! I don't have your credentials yet. Please log into the VibeCoder Web UI and link your Slack Member ID: `{user_id}`"
        }
        
    feature_description = text.strip()
    if not feature_description:
        return {
            "response_type": "ephemeral",
            "text": "Please provide a description. Example: `/vibecoder Add a dark mode toggle`"
        }

    try:
        jira_client = JIRA(server=session_data["jira_url"], basic_auth=(session_data["jira_user"], session_data["jira_token"]))
        
        first_line = feature_description.split('\n')[0].strip()
        summary = first_line[:50] + ("..." if len(first_line) > 50 else "")
        issue_dict = {
            'project': {'key': session_data["jira_project_key"]},
            'summary': f"Slack Req: {summary}",
            'description': feature_description,
            'issuetype': {'name': 'Task'}, 
        }
        new_issue = jira_client.create_issue(fields=issue_dict)
        ticket_id = new_issue.key
    except Exception as e:
        return {"response_type": "ephemeral", "text": f"❌ Failed to create Jira ticket. Error: {str(e)}"}

    workspace = WorkspaceManager(
        session_data["repo_url"], 
        session_data["github_token"], 
        session_id=session_data.get("session_id", user_id)
    )

    background_tasks.add_task(slack_autopilot_worker, ticket_id, feature_description, session_data, workspace)

    return {
        "response_type": "in_channel",
        "text": f"🚀 Request received, {user_name}!\n✅ Created Jira ticket `{ticket_id}`.\n⏳ The AI is currently analyzing the codebase and will open a GitHub PR shortly."
    }