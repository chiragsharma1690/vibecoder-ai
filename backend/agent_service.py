import os
import json
import ollama
from fastapi import HTTPException
from jira import JIRA

from schemas import ExecuteRequest, PlanRequest
from workspace_manager import WorkspaceManager

# ---------------- PLANNING AGENT ---------------- #
def generate_architect_plan(request: PlanRequest, session: dict, workspace: WorkspaceManager):
    """Handles the Jira fetch and JSON plan generation."""
    try:
        jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
        issue = jira_client.issue(request.ticket_id)
        jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Jira ticket: {str(e)}")

    repo_tree = workspace.get_repo_tree()
    prompt = f"You are an expert AI Software Architect.\nJIRA TICKET ({request.ticket_id}):\n{jira_context}\nCURRENT REPOSITORY STRUCTURE:\n{repo_tree}\n"

    # Inject feedback loop if this is a revision request
    if request.feedback and request.previous_plan:
        prompt += f"PREVIOUS PLAN:\n{json.dumps(request.previous_plan, indent=2)}\nUSER FEEDBACK:\n{request.feedback}\nYour task is to revise the previous plan based STRICTLY on the user feedback.\n"
    else:
        prompt += "Your task is to analyze the ticket and the repository structure, and output a strict JSON plan of action.\n"

    prompt += "Do not include conversational text. You must respond ONLY with a valid JSON object matching this exact schema: {\"strategy\": \"...\", \"files_to_modify\": [], \"new_files\": [], \"commands_to_run\": []}"

    print("🧠 Architect Agent is planning...")
    target_model = "qwen2.5-coder:7b"
    
    try:
        response = ollama.generate(
            model=target_model, 
            prompt=prompt, 
            format="json", 
            options={"temperature": 0.1, "num_ctx": 8192}
        )
        raw_response = response.get("response", "").strip()
        
        if not raw_response: 
            raise ValueError(f"Ollama returned an empty string. Make sure '{target_model}' is installed.")
            
        if raw_response.startswith("```"): 
            raw_response = raw_response.replace("```json", "").replace("```", "").strip()
            
        return json.loads(raw_response)
        
    except json.JSONDecodeError:
        print(f"⚠️ RAW INVALID OLLAMA OUTPUT:\n{raw_response}")
        raise HTTPException(status_code=500, detail="LLM did not return valid JSON.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama Error: {str(e)}")


# ---------------- MULTI-AGENT EXECUTION LOOP ---------------- #
def compile_developer_prompt(ticket_id, plan, session, workspace):
    """Compiles the context needed for the developer LLM."""
    jira_client = JIRA(server=session["jira_url"], basic_auth=(session["jira_user"], session["jira_token"]))
    issue = jira_client.issue(ticket_id)
    jira_context = f"Summary: {issue.fields.summary}\nDescription: {issue.fields.description}"
    
    return f"""
    You are the Lead Developer Agent. Implement this approved plan.
    JIRA TICKET:\n{jira_context}
    APPROVED PLAN:\n{json.dumps(plan, indent=2)}
    CURRENT REPOSITORY STRUCTURE:\n{workspace.get_repo_tree()}
    
    INSTRUCTIONS:
    1. Write the complete, fully-functional code.
    2. Respond ONLY with the files in this exact format:
    ---FILE: path/to/file.ext---
    content
    ---END---
    """

def run_multi_agent_loop(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    """The core execution loop used by both Sync and Async modes."""
    developer_prompt = compile_developer_prompt(request.ticket_id, request.plan, session, workspace)
    max_attempts = 3
    saved_files = []
    qa_passed = False
    qa_logs = []

    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 --- AGENT LOOP ATTEMPT {attempt} ---")
        print("💻 Developer Agent is writing code...")
        
        try:
            response = ollama.generate(
                model="qwen2.5-coder:7b", 
                prompt=developer_prompt, 
                options={"temperature": 0.1, "num_ctx": 8192}
            )
            raw_text = response.get("response", "")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")

        # Parse AI Output
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
                    
                if path not in saved_files: 
                    saved_files.append(path)

        # Run Setup Commands (Only on attempt 1)
        if attempt == 1:
            commands = request.plan.get("commands_to_run", [])
            if commands:
                success, output = workspace.run_shell_command(" && ".join(commands))
                if not success: 
                    raise HTTPException(status_code=500, detail=f"System command failed: {output}")

        # QA Agent Validation
        qa_success, qa_output = workspace.run_qa_agent()
        qa_logs.append(qa_output)

        if qa_success:
            print("🎉 QA Agent approved the build!")
            qa_passed = True
            break
        else:
            print(f"❌ QA Agent found bugs:\n{qa_output[:300]}...")
            if attempt < max_attempts:
                # Provide feedback loop to LLM
                developer_prompt = f"You are the Lead Developer Agent. Your previous code submission failed QA validation.\nQA AGENT ERROR REPORT:\n{qa_output}\nAnalyze the error, fix the bugs in your code, and output the corrected files using the exact ---FILE: path--- format."
            else:
                print("🛑 Max attempts reached. Agent could not fix the bug.")

    if not saved_files:
        raise HTTPException(status_code=500, detail="The Developer Agent failed to format the files correctly.")

    return saved_files, qa_passed, qa_logs


# ---------------- BACKGROUND WORKER (ASYNC MODE) ---------------- #
def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    """The heavy-lifting background task for Async Mode."""
    base_branch = session.get("base_branch", "main")
    branch_name = workspace.setup_branch(request.ticket_id, base_branch)
    
    # Run the shared loop
    saved_files, qa_passed, qa_logs = run_multi_agent_loop(request, session, workspace)

    # Git Operations
    workspace.run_git_command("add", ".")
    workspace.run_git_command("commit", "-m", f"Auto-implemented {request.ticket_id}")
    workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
    
    # Dev Server Screenshot
    workspace.capture_dev_screenshot()
    
    # Open Pull Request
    pr_body = f"""### 🤖 VibeCoder AI Implementation
Resolves Jira Ticket: **{request.ticket_id}**

**Implementation Details:**
* Strategy: {request.plan.get('strategy', 'N/A')}
* Tests Passed: {'Yes' if qa_passed else 'Failed / Skipped'} (Automated QA Agent)

> *Note: Screenshot of dev environment has been committed to `.agent/preview.png`*
"""
    pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id} Implementation", pr_body)
    print(f"✨ ASYNC MISSION COMPLETE! PR: {pr_url}")