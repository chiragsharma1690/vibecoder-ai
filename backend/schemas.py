from pydantic import BaseModel
from typing import Optional, Dict, Any

# ---------------------------------------------------------
# Pydantic Schemas for strict FastAPI payload validation
# ---------------------------------------------------------

class ConnectRequest(BaseModel):
    """Payload required to initialize connection to Jira and GitHub."""
    github_token: str
    jira_url: str
    jira_user: str
    jira_token: str
    repo_url: str

class PlanRequest(BaseModel):
    """Payload for generating or revising an Architect's plan."""
    ticket_id: str
    feedback: Optional[str] = None
    previous_plan: Optional[Dict[str, Any]] = None

class ExecuteRequest(BaseModel):
    """Payload to trigger the Multi-Agent coding pipeline."""
    ticket_id: str
    plan: Dict[str, Any]
    async_mode: bool = False

class PushRequest(BaseModel):
    """Payload to manually approve and push synchronous code."""
    ticket_id: str

class SetBranchRequest(BaseModel):
    """Payload to update the base branch for operations."""
    branch_name: str