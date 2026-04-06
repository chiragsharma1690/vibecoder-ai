import json
from app.agents.base import call_llm

def generate_architect_plan(ticket_id: str, jira_context: str, repo_tree: str, feedback: str = None, previous_plan: dict = None):
    """The Architect Agent. Generates strict JSON defining the architectural approach."""
    prompt = f"You are an expert AI Software Architect.\nJIRA TICKET ({ticket_id}):\n{jira_context}\nCURRENT REPOSITORY STRUCTURE:\n{repo_tree}\n"
    
    if feedback and previous_plan:
        prompt += f"PREVIOUS PLAN:\n{json.dumps(previous_plan, indent=2)}\nUSER FEEDBACK:\n{feedback}\nRevise the plan based STRICTLY on the feedback.\n"
    else:
        prompt += "Analyze the ticket and repository, and output a strict JSON plan.\n"

    prompt += """
    Respond ONLY with a valid JSON object matching this exact schema:
    {
        "strategy": "Detailed explanation of the solution.", 
        "files_to_modify": ["path/to/existing_file.ext"], 
        "new_files": ["path/to/new_file.ext"], 
        "commands_to_run": ["<shell command>"]
    }
    
    CRITICAL RULES FOR PROJECT SETUP:
    1. NEVER use interactive commands. You MUST use unattended flags (e.g., -y, --yes, --silent). For npx, use `npx --yes`.
    2. FOLDERS: You MUST use `mkdir -p` (e.g., `mkdir -p src/components`) to prevent missing parent directory errors.
    3. INITIALIZATION: If this is a blank project, ensure you initialize it first (e.g., `npm init -y`) before installing packages.
    4. Be EXHAUSTIVE. Explicitly list EVERY necessary configuration file.
    5. Provide EXACT file paths.
    6. DIRECTORY MATCHING: Inspect the CURRENT REPOSITORY STRUCTURE. Place new files inside EXISTING folders where applicable.
    7. TECH STACK AWARENESS: Analyze the repository tree to determine the correct language and package manager.
    """
    print("🧠 Architect Agent is planning...")
    return json.loads(call_llm(prompt, format_type="json"))