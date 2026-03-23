import os
import shutil
import subprocess
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jira import JIRA
import json
import ollama
from typing import Optional, Dict, Any

from workspace_manager import WorkspaceManager

# Initialize the app
app = FastAPI(title="VibeCoder AI API")

# Configure CORS to allow your local React frontend to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for Data Validation ---
class ConnectRequest(BaseModel):
    github_token: str
    jira_url: str
    jira_user: str
    jira_token: str
    repo_url: str

class PlanRequest(BaseModel):
    ticket_id: str
    feedback: Optional[str] = None
    previous_plan: Optional[Dict[str, Any]] = None

class ExecuteRequest(BaseModel):
    ticket_id: str
    plan: Dict[str, Any]  # Receives the JSON plan approved by the user

class PushRequest(BaseModel):
    ticket_id: str

class SetBranchRequest(BaseModel):
    branch_name: str


# --- Helper Functions ---

def get_auth_repo_url(repo_url: str, token: str) -> str:
    """Injects the GitHub token securely into the clone URL."""
    if not repo_url.endswith(".git"):
        repo_url += ".git"
        
    parsed = urlparse(repo_url)
    # Rebuild URL with authentication: https://x-access-token:TOKEN@github.com/user/repo.git
    return f"{parsed.scheme}://x-access-token:{token}@{parsed.netloc}{parsed.path}"

SESSION_FILE = os.path.join(os.getcwd(), "workspaces", "session.json")

def save_session(data: dict):
    """Saves active credentials and workspace info to a local file."""
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)

def load_session() -> dict:
    """Loads active credentials."""
    if not os.path.exists(SESSION_FILE):
        raise HTTPException(status_code=400, detail="No active session. Please connect first.")
    with open(SESSION_FILE, "r") as f:
        return json.load(f)


# --- API Endpoints ---

@app.get("/")
async def health_check():
    """Simple check to ensure the server is running."""
    return {"status": "active", "message": "VibeCoder Backend is alive."}

@app.post("/api/connect")
async def connect_workspace(request: ConnectRequest):
    """Validates credentials and clones the repository into /workspaces."""
    
    # 1. Validate Jira Credentials
    try:
        jira_client = JIRA(
            server=request.jira_url, 
            basic_auth=(request.jira_user, request.jira_token)
        )
        jira_client.myself()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Jira Authentication Failed. Error: {str(e)}")

    # 2. Initialize Workspace Manager
    workspace = WorkspaceManager(request.repo_url, request.github_token)

    # 3. Validate GitHub Access
    if not workspace.verify_access():
        raise HTTPException(status_code=401, detail="GitHub Authentication Failed. Check your Token and Repo URL.")

    # 4. Clone the Repo
    try:
        repo_path = workspace.setup_workspace()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clone repository: {str(e)}")
    
    # 5. Save the session for future requests
    save_session({
        "github_token": request.github_token,
        "jira_url": request.jira_url,
        "jira_user": request.jira_user,
        "jira_token": request.jira_token,
        "repo_url": request.repo_url,
        "repo_name": workspace.repo_name
    })

    # Get all branches to send to the UI
    branches = workspace.get_available_branches()

    return {
        "status": "success", 
        "message": f"Successfully connected to {workspace.repo_name}.",
        "workspace_path": repo_path,
        "branches": branches # NEW: Send branches to UI
    }

@app.post("/api/set-branch")
async def set_base_branch(request: SetBranchRequest):
    """Checks out the user's selected branch to use as the base for the agent."""
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    try:
        workspace.checkout_base_branch(request.branch_name)
        
        # Save the selected base branch into the session
        session["base_branch"] = request.branch_name
        save_session(session)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to checkout branch {request.branch_name}: {str(e)}")

    return {"status": "success", "message": f"Switched to base branch: {request.branch_name}"}

@app.post("/api/chat/plan")
async def generate_plan(request: PlanRequest):
    """Fetches Jira data, reads local repo, and asks Ollama for a JSON plan."""
    session = load_session()
    
    # 1. Fetch Jira Context
    try:
        jira_client = JIRA(
            server=session["jira_url"], 
            basic_auth=(session["jira_user"], session["jira_token"])
        )
        issue = jira_client.issue(request.ticket_id)
        jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Jira ticket: {str(e)}")

    # 2. Get Codebase Context
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    repo_tree = workspace.get_repo_tree()

    # 3. Compile the Prompt
    prompt = f"""
    You are an expert AI Software Architect.
    
    JIRA TICKET ({request.ticket_id}):
    {jira_context}
    
    CURRENT REPOSITORY STRUCTURE:
    {repo_tree}
    
    Your task is to analyze the ticket and the repository structure, and output a strict JSON plan of action.
    Do not include any conversational text, markdown formatting, or explanations outside the JSON object.
    
    You must respond ONLY with a valid JSON object matching this exact schema:
    {{
        "strategy": "A 2-3 sentence explanation of how you will solve this ticket.",
        "files_to_modify": ["path/to/existing/file.ext"],
        "new_files": ["path/to/new/file.ext"],
        "commands_to_run": ["npm install x", "pip install y"]
    }}
    """

    # 4. Query Ollama (Enforcing JSON Format)
    try:
        response = ollama.generate(
            model="qwen2.5-coder:7b",
            prompt=prompt,
            format="json",  # This strictly forces the LLM to output valid JSON
            options={
                "temperature": 0.1, # Keep it deterministic and logical
                "num_ctx": 8192
            }
        )
        
        # Parse the JSON response
        raw_plan = response.get("response", "{}")
        plan_data = json.loads(raw_plan)
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="LLM failed to generate a valid JSON plan.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama Error: {str(e)}")

    # 5. Return the structured plan to the UI
    return {
        "status": "success", 
        "ticket_id": request.ticket_id,
        "plan": plan_data
    }

@app.post("/api/chat/execute")
async def execute_plan(request: ExecuteRequest):
    """Executes the approved AI plan, writes files, and runs the QA loop."""
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    # 1. Setup Branch
    branch_name = workspace.setup_branch(request.ticket_id)

    # 2. Fetch Jira Context (so the coder has the full requirements)
    try:
        jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
        issue = jira_client.issue(request.ticket_id)
        jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Jira fetch failed: {str(e)}")

    # 3. Read Codebase Context
    repo_tree = workspace.get_repo_tree()

    # 4. Construct the Coder Prompt
    plan_json = json.dumps(request.plan, indent=2)
    prompt = f"""
    You are a Senior Software Engineer. Your task is to implement the following approved plan.
    
    JIRA TICKET:
    {jira_context}
    
    APPROVED PLAN:
    {plan_json}
    
    CURRENT REPOSITORY STRUCTURE:
    {repo_tree}
    
    INSTRUCTIONS:
    1. Write the complete, fully-functional code for the files listed in the plan.
    2. Write unit tests for the new functionality.
    3. Respond ONLY with the files in this exact format:
    ---FILE: path/to/file.ext---
    content
    ---END---
    """

    # 5. Generate Code via Ollama
    print("🧠 LLM is writing code based on the approved plan...")
    try:
        response = ollama.generate(
            model="qwen2.5-coder:7b",
            prompt=prompt,
            options={"temperature": 0.1, "num_ctx": 8192}
        )
        raw_text = response.get("response", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama failed to generate code: {str(e)}")

    # 6. Parse and Save Files to Disk
    saved_files = []
    if "---FILE:" in raw_text:
        parts = raw_text.split("---FILE:")
        for part in parts[1:]:
            if "---" not in part or "---END---" not in part:
                continue
            
            # Extract path and content safely
            path = part.split("---")[0].strip().strip("`'\" \n")
            content = part.split("---")[1].split("---END---")[0].strip()
            
            full_path = os.path.join(workspace.repo_path, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            saved_files.append(path)

    if not saved_files:
        raise HTTPException(status_code=500, detail="The LLM failed to output correctly formatted files.")

    # 7. Execute System Commands (e.g., npm install)
    execution_logs = []
    commands = request.plan.get("commands_to_run", [])
    if commands:
        chained_cmd = " && ".join(commands)
        print(f"🚀 Running commands: {chained_cmd}")
        success, output = workspace.run_shell_command(chained_cmd)
        execution_logs.append({"command": chained_cmd, "success": success, "output": output[:500]})
        
        # If install fails, we should abort before testing
        if not success:
            raise HTTPException(status_code=500, detail=f"System command failed: {output}")

    # 8. Automated QA / Testing Loop
    # We attempt to run standard testing commands. Adjust based on your primary tech stack.
    test_cmd = "npm run test --passWithNoTests" if os.path.exists(os.path.join(workspace.repo_path, "package.json")) else "pytest"
    print(f"🧪 Running QA check: {test_cmd}")
    
    test_success, test_output = workspace.run_shell_command(test_cmd)
    
    if not test_success:
        print("🩹 Tests failed. Attempting self-healing...")
        # Self-Healing Prompt
        heal_prompt = f"""
        You recently wrote code that failed the test suite. 
        
        FAILED TEST OUTPUT:
        {test_output}
        
        Please analyze the error and output the corrected file(s) using the exact same ---FILE: path--- format.
        """
        heal_response = ollama.generate(model="qwen2.5-coder:7b", prompt=heal_prompt)
        
        # We re-parse the healed files (condensed logic for brevity)
        if "---FILE:" in heal_response.get("response", ""):
            parts = heal_response["response"].split("---FILE:")
            for part in parts[1:]:
                if "---END---" in part:
                    path = part.split("---")[0].strip()
                    content = part.split("---")[1].split("---END---")[0].strip()
                    with open(os.path.join(workspace.repo_path, path), "w", encoding="utf-8") as f:
                        f.write(content)
                        
            # Re-run tests after healing
            test_success, test_output = workspace.run_shell_command(test_cmd)

    return {
        "status": "success", 
        "message": "Code generated and validated.",
        "files_created": saved_files,
        "test_passed": test_success,
        "logs": execution_logs
    }

@app.post("/api/chat/push")
async def push_code(request: PushRequest):
    """Commits and pushes the finalized code to GitHub."""
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    branch_name = f"feat-{request.ticket_id.lower()}"
    
    # 1. Stage all changes
    workspace.run_git_command("add", ".")
    
    # 2. Check if there are actually changes to commit
    status = workspace.run_git_command("status", "--porcelain")
    if not status.stdout.strip():
        return {
            "status": "skipped", 
            "message": "Git reports no changes. The generated code might be identical to existing files."
        }
        
    # 3. Commit the code
    commit_msg = f"Auto-implementation of {request.ticket_id}"
    commit_result = workspace.run_git_command("commit", "-m", commit_msg)
    
    if commit_result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Failed to commit code: {commit_result.stderr}")
        
    # 4. Push to remote
    print(f"🚀 Pushing branch '{branch_name}' to remote...")
    push_result = workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
    
    if push_result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Failed to push to GitHub: {push_result.stderr}")

    return {
        "status": "success", 
        "message": f"Successfully pushed all changes to GitHub!",
        "branch": branch_name,
        "repo_name": workspace.repo_name
    }

if __name__ == "__main__":
    import uvicorn
    # Run the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)