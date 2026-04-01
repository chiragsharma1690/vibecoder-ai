from fastapi import APIRouter, BackgroundTasks, Form
from jira import JIRA

# from app.core.session import load_session
from app.core.workspace import WorkspaceManager
from app.services.pipeline import slack_autopilot_worker

# Prefix saves us from typing /api/webhooks on every route
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# TODO: correction later
# @router.post("/slack")
# async def slack_webhook(
#     background_tasks: BackgroundTasks,
#     text: str = Form(...),         # The prompt written by the user in Slack
#     user_name: str = Form(...)     # The Slack username who triggered it
# ):
#     """Listens for Slack Slash Commands to autonomously build features."""
#     session = load_session()
#     workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
#     # Fallback to 'KAN' if a project key wasn't set, though it should be from the connect phase
#     project_key = session.get("jira_project_key", "KAN")

#     try:
#         # 1. Autonomously Create the Jira Ticket
#         jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
#         issue_dict = {
#             'project': {'key': project_key},
#             'summary': f"Slack Request from @{user_name}",
#             'description': text,
#             'issuetype': {'name': 'Task'},
#         }
#         new_issue = jira_client.create_issue(fields=issue_dict)
#         ticket_id = new_issue.key

#         # 2. Trigger the Autopilot in the background
#         background_tasks.add_task(slack_autopilot_worker, ticket_id, text, session, workspace)

#         # 3. Respond instantly to Slack
#         return {
#             "response_type": "in_channel",
#             "text": f"🚀 *VibeCoder AI* is on it!\n✅ Created Jira Ticket: `<{session['jira_url']}/browse/{ticket_id}|{ticket_id}>`\n💻 Generating architecture plan and writing code..."
#         }
#     except Exception as e:
#         return {"response_type": "ephemeral", "text": f"⚠️ VibeCoder failed to start: {str(e)}"}

@router.post("/slack")
async def slack_webhook(
    background_tasks: BackgroundTasks,
    text: str = Form(...),         
    user_name: str = Form(...)     
):
    """
    Listens for Slack Slash Commands.
    NOTE: Because the app is now a modern stateless architecture, 
    Slack commands require a Database to map Slack IDs to API tokens.
    """
    
    # We return a graceful error message directly to the Slack user
    return {
        "response_type": "ephemeral",
        "text": (
            "⚠️ *VibeCoder Architecture Update:*\n"
            "We have upgraded to a secure, stateless frontend-cookie architecture. "
            "To trigger AI agents from Slack, please connect a Database to store user tokens. "
            "For now, please use the Web UI!"
        )
    }