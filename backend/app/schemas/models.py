from pydantic import BaseModel
from typing import Optional, Dict, Any

class ConnectRequest(BaseModel):
    jira_url: str
    jira_user: str
    jira_token: str
    repo_url: str
    github_token: str

class SetBranchRequest(BaseModel):
    branch_name: str

class PlanRequest(BaseModel):
    ticket_id: str
    feedback: Optional[str] = None
    previous_plan: Optional[Dict[str, Any]] = None

class ExecuteRequest(BaseModel):
    ticket_id: str
    plan: Dict[str, Any]
    async_mode: bool = True

class PushRequest(BaseModel):
    ticket_id: str