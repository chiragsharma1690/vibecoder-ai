from fastapi import APIRouter, BackgroundTasks, Form, Depends, HTTPException
from pydantic import BaseModel
from jira import JIRA

from app.core.database import get_slack_user, save_slack_user
from app.core.dependencies import get_current_session
from app.schemas.models import ExecuteRequest, LinkSlackRequest
from app.core.workspace import WorkspaceManager

from app.agents.architect import generate_architect_plan
from app.services.pipeline import run_multi_agent_loop

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# ---------------------------------------------------------
# 1. THE END-TO-END BACKGROUND WORKER
# ---------------------------------------------------------
def run_full_slack_pipeline(ticket_id: str, description: str, session_data: dict):
    """Orchestrates the entire AI pipeline: Plan -> Code -> Push"""
    try:
        workspace = WorkspaceManager(session_data["repo_url"], session_data["github_token"])
        base_branch = session_data.get("base_branch", "main")
        
        # 1. Setup Branch locally
        workspace.setup_branch(ticket_id, base_branch)
        
        # 2. Architect Phase: Generate the Plan
        print(f"[{ticket_id}] Generating Architect Plan...")
        jira_context = f"Description: {description}"
        plan_data = generate_architect_plan(
            ticket_id=ticket_id, 
            jira_context=jira_context, 
            repo_tree=workspace.get_repo_tree()
        )
        
        # 3. Execute Phase: Run the Coder loop
        print(f"[{ticket_id}] Executing Plan locally...")
        exec_req = ExecuteRequest(ticket_id=ticket_id, plan=plan_data, async_mode=True)
        run_multi_agent_loop(exec_req, session_data, workspace)
        
        # 4. Push Phase: Commit and Push to GitHub
        print(f"[{ticket_id}] Pushing to GitHub...")
        branch_name = workspace.run_git_command("branch", "--show-current").stdout.strip()
        workspace.run_git_command("add", ".")
        
        # Only commit if there are actually changes
        if workspace.run_git_command("status", "--porcelain").stdout.strip():
            workspace.run_git_command("commit", "-m", f"Auto-implementation of {ticket_id} via Slack")
            workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
            print(f"[{ticket_id}] Pipeline Complete! Code pushed to {branch_name}.")
        else:
            print(f"[{ticket_id}] No code changes were detected.")
            
    except Exception as e:
        print(f"[{ticket_id}] ❌ Pipeline Error: {str(e)}")
        # In a production app, you would use a Slack Webhook URL to send this error back to the channel!


# ---------------------------------------------------------
# 2. FRONTEND ENDPOINT: Link the Slack ID
# ---------------------------------------------------------
@router.post("/slack/link")
async def link_slack_account(request: LinkSlackRequest, session: dict = Depends(get_current_session)):
    try:
        save_slack_user(request.slack_user_id, session)
        return {"status": "success", "message": f"Successfully linked Slack ID {request.slack_user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ---------------------------------------------------------
# 3. WEBHOOK ENDPOINT: Listen to Slack Slash Commands
# ---------------------------------------------------------
@router.post("/slack")
async def slack_webhook(
    background_tasks: BackgroundTasks,
    text: str = Form(...),         
    user_id: str = Form(...), 
    user_name: str = Form(...)     
):
    # Look up credentials
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

    # Create the Jira Ticket
    try:
        jira_client = JIRA(server=session_data["jira_url"], basic_auth=(session_data["jira_user"], session_data["jira_token"]))
        summary = feature_description[:50] + ("..." if len(feature_description) > 50 else "")
        issue_dict = {
            'project': {'key': session_data["jira_project_key"]},
            'summary': f"Slack Req: {summary}",
            'description': feature_description,
            'issuetype': {'name': 'Task'}, 
        }
        new_issue = jira_client.create_issue(fields=issue_dict)
        ticket_id = new_issue.key
    except Exception as e:
        return {
            "response_type": "ephemeral",
            "text": f"❌ Failed to create Jira ticket. Error: {str(e)}"
        }

    background_tasks.add_task(run_full_slack_pipeline, ticket_id, feature_description, session_data)

    return {
        "response_type": "in_channel",
        "text": f"🚀 Request received, {user_name}!\n✅ Created Jira ticket `{ticket_id}`.\n⏳ The AI Architect is generating a plan, executing code, and will push a PR to GitHub shortly."
    }