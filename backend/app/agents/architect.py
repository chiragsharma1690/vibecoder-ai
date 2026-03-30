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
        "commands_to_run": ["npm install package_name"], 
        "ui_components_to_screenshot": [{"route": "/path", "selector": "#id"}]
    }
    
    CRITICAL RULES FOR PROJECT SETUP:
    1. NEVER use interactive commands. You MUST use unattended/silent flags.
    2. Be EXHAUSTIVE. Explicitly list EVERY necessary configuration file.
    3. If dependencies are needed, provide REAL package manager commands.
    4. Provide EXACT file paths.
    5. DIRECTORY MATCHING: You MUST inspect the CURRENT REPOSITORY STRUCTURE. Place new files inside EXISTING folders.
    """
    print("🧠 Architect Agent is planning...")
    return json.loads(call_llm(prompt, format_type="json"))