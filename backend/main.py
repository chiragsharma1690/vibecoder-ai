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
    """Fetches Jira context, reads repo, and generates (or revises) a JSON plan."""
    session = load_session()
    
    # 1. Fetch Jira Context
    try:
        jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
        issue = jira_client.issue(request.ticket_id)
        jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Jira ticket: {str(e)}")

    # 2. Get Codebase Context
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    repo_tree = workspace.get_repo_tree()

    # 3. Compile the Architect Prompt
    prompt = f"""
    You are an expert AI Software Architect.
    
    JIRA TICKET ({request.ticket_id}):
    {jira_context}
    
    CURRENT REPOSITORY STRUCTURE:
    {repo_tree}
    """

    # Inject the feedback loop if the user is modifying an existing plan
    if request.feedback and request.previous_plan:
        prompt += f"""
        PREVIOUS PLAN:
        {json.dumps(request.previous_plan, indent=2)}
        
        USER FEEDBACK:
        {request.feedback}
        
        Your task is to revise the previous plan based STRICTLY on the user feedback.
        """
    else:
        prompt += """
        Your task is to analyze the ticket and the repository structure, and output a strict JSON plan of action.
        """

    prompt += """
    Do not include any conversational text, markdown formatting, or explanations outside the JSON object.
    You must respond ONLY with a valid JSON object matching this exact schema:
    {
        "strategy": "A 2-3 sentence explanation of how you will solve this.",
        "files_to_modify": ["path/to/existing/file.ext"],
        "new_files": ["path/to/new/file.ext"],
        "commands_to_run": ["npm install x"]
    }
    """

    # 4. Query Ollama
    print("🧠 Architect Agent is planning...")
    try:
        response = ollama.generate(
            model="qwen3.5:9b",
            prompt=prompt,
            format="json",
            options={"temperature": 0.1, "num_ctx": 8192}
        )
        plan_data = json.loads(response.get("response", "{}"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama Error: {str(e)}")

    return {
        "status": "success", 
        "ticket_id": request.ticket_id,
        "plan": plan_data,
        "is_revision": bool(request.feedback)
    }

@app.post("/api/chat/execute")
async def execute_plan(request: ExecuteRequest):
    """Multi-Agent Loop: Developer writes code -> QA tests it -> Developer fixes bugs."""
    session = load_session()
    workspace = WorkspaceManager(session["repo_url"], session["github_token"])
    
    # 1. Setup Branch
    base_branch = session.get("base_branch", "main")
    branch_name = workspace.setup_branch(request.ticket_id, base_branch)

    # 2. Fetch Jira & Codebase Context
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(request.ticket_id)
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    repo_tree = workspace.get_repo_tree()

    # 3. Base Developer Prompt
    plan_json = json.dumps(request.plan, indent=2)
    developer_prompt = f"""
    You are the Lead Developer Agent. Implement this approved plan.
    
    JIRA TICKET:
    {jira_context}
    
    APPROVED PLAN:
    {plan_json}
    
    CURRENT REPOSITORY STRUCTURE:
    {repo_tree}
    
    INSTRUCTIONS:
    1. Write the complete, fully-functional code.
    2. Respond ONLY with the files in this exact format:
    ---FILE: path/to/file.ext---
    content
    ---END---
    """

    max_attempts = 3
    saved_files = []
    qa_passed = False
    qa_logs = []

    # --- MULTI-AGENT LOOP ---
    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 --- AGENT LOOP ATTEMPT {attempt} ---")
        
        # Step A: Developer Agent Writes Code
        print("💻 Developer Agent is writing code...")
        try:
            response = ollama.generate(
                model="qwen3.5:9b",
                prompt=developer_prompt,
                options={"temperature": 0.1, "num_ctx": 8192}
            )
            raw_text = response.get("response", "")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")

        # Step B: Parse and Save Files
        if "---FILE:" in raw_text:
            parts = raw_text.split("---FILE:")
            for part in parts[1:]:
                if "---END---" not in part: continue
                path = part.split("---")[0].strip().strip("`'\" \n")
                content = part.split("---")[1].split("---END---")[0].strip()
                
                full_path = os.path.join(workspace.repo_path, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                if path not in saved_files: saved_files.append(path)

        # Step C: Run System Commands (e.g., npm install) ONCE
        if attempt == 1:
            commands = request.plan.get("commands_to_run", [])
            if commands:
                chained_cmd = " && ".join(commands)
                print(f"🚀 Running setup commands: {chained_cmd}")
                success, output = workspace.run_shell_command(chained_cmd)
                if not success:
                    raise HTTPException(status_code=500, detail=f"System command failed: {output}")

        # Step D: QA Agent Evaluates
        qa_success, qa_output = workspace.run_qa_agent()
        qa_logs.append(qa_output)

        if qa_success:
            print("🎉 QA Agent approved the build!")
            qa_passed = True
            break
        else:
            print(f"❌ QA Agent found bugs:\n{qa_output[:300]}...")
            if attempt < max_attempts:
                # Step E: Feedback loop back to Developer Agent
                developer_prompt = f"""
                You are the Lead Developer Agent. Your previous code submission failed QA validation.
                
                QA AGENT ERROR REPORT:
                {qa_output}
                
                Analyze the error, fix the bugs in your code, and output the corrected files using the exact ---FILE: path--- format.
                """
            else:
                print("🛑 Max attempts reached. Agent could not fix the bug.")

    if not saved_files:
        raise HTTPException(status_code=500, detail="The Developer Agent failed to format the files correctly.")

    # 9. Extract the Diffs for the Frontend
    file_diffs = workspace.get_file_diffs(saved_files)

    return {
        "status": "success", 
        "message": f"Execution finished. QA Passed: {qa_passed}. (Took {attempt} attempts).",
        "files_created": saved_files,
        "test_passed": qa_passed,
        "qa_logs": qa_logs,
        "file_diffs": file_diffs
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