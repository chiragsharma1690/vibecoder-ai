import os
import json
import ollama
import concurrent.futures

def call_llm(prompt: str, format_type=None, temperature=0.1, model="qwen2.5-coder:7b", timeout=180):
    """Standardized wrapper for Ollama calls with a strict compute timeout."""
    options = {"temperature": temperature, "num_ctx": 8192}
    
    def _generate():
        return ollama.generate(model=model, prompt=prompt, format=format_type, options=options)
        
    try:
        # Wrap the LLM call in a strict timeout to prevent infinite compute hangs
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_generate)
            response = future.result(timeout=timeout) # Kills the wait after 180 seconds
            
        raw = response.get("response", "").strip()
        
        # Strip top-level markdown wraps
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]).strip()
            
        if not raw: raise ValueError(f"Model returned empty string.")
        return raw
        
    except concurrent.futures.TimeoutError:
        raise ValueError(f"LLM Generation timed out after {timeout} seconds. The model got stuck.")
    except Exception as e:
        raise ValueError(f"LLM Error: {str(e)}")

def extract_and_save_files(raw_text: str, repo_path: str, saved_files: list):
    """Parses ---FILE: path--- blocks, aggressively cleans rogue markdown, and securely saves them."""
    if "---FILE:" not in raw_text: 
        return
        
    parts = raw_text.split("---FILE:")
    for part in parts[1:]:
        if not part.strip(): continue
        
        if "---END---" not in part:
            raise ValueError("LLM generation was truncated before completion. Try writing more concise code or increase max tokens.")
            
        raw_path = part.split("---")[0].strip().strip("`'\" \n")
        content = part.split("---")[1].split("---END---")[0].strip()
        
        # Resolve the absolute paths and ensure the target file lives INSIDE the repo path
        full_path = os.path.abspath(os.path.join(repo_path, raw_path))
        repo_abs_path = os.path.abspath(repo_path)
        
        if not full_path.startswith(repo_abs_path):
            raise ValueError(f"Security Alert: Agent attempted Path Traversal outside workspace directory: {raw_path}")
            
        # Strip rogue markdown wrappers from the content
        if content.startswith("```"):
            first_newline_idx = content.find("\n")
            if first_newline_idx != -1:
                content = content[first_newline_idx+1:]
        if content.endswith("```"):
            content = content[:-3].strip()
        
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f: 
            f.write(content.strip() + "\n")
            
        if raw_path not in saved_files: 
            saved_files.append(raw_path)

# --- THE AGENTS ---

def generate_architect_plan(ticket_id: str, jira_context: str, repo_tree: str, feedback: str = None, previous_plan: dict = None):
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
    1. NEVER use interactive commands. You MUST use unattended/silent flags (e.g., `npm init -y`, `npm create vite@latest . -- --template react`, `pip install -q`).
    2. Be EXHAUSTIVE. If bootstrapping a new project without a CLI tool, you must explicitly list EVERY necessary configuration file (e.g., package.json, requirements.txt, .env) in the `new_files` array.
    3. If dependencies are needed, provide REAL package manager commands based on the repo structure. 
    4. Provide EXACT file paths as they will appear in the repository tree.
    """
    print("🧠 Architect Agent is planning...")
    return json.loads(call_llm(prompt, format_type="json"))

def run_developer_agent(prompt: str, repo_path: str, saved_files: list):
    print("💻 Developer Agent is writing implementation code...")
    raw_text = call_llm(prompt)
    extract_and_save_files(raw_text, repo_path, saved_files)

def generate_qa_command(saved_files: list, repo_tree: str, repo_path: str, last_qa_error: str):
    print("🧪 QA Engineer Agent is writing unit tests...")
    qa_feedback = f"\n🚨 PREVIOUS TEST FAILED:\n{last_qa_error}\nFix the testing code or terminal command!\n" if last_qa_error else ""
    
    qa_prompt = f"""
    You are the QA Automation Engineer. Modified files: {saved_files}.
    CURRENT REPOSITORY STRUCTURE:\n{repo_tree}\n{qa_feedback}
    
    INSTRUCTIONS:
    1. Write unit tests for modified code (>80% coverage).
    2. Provide EXACT terminal command to install dependencies AND run tests with coverage (Do NOT rely on existing package scripts).
    3. Respond EXACTLY in this format. DO NOT use markdown code blocks (```) inside the file content.
    ---TEST_COMMAND: <your explicit command>---
    ---FILE: path/to/test.ext---
    code
    ---END---
    """
    qa_raw_text = call_llm(qa_prompt)
    extract_and_save_files(qa_raw_text, repo_path, saved_files)

    test_cmd = ""
    if "---TEST_COMMAND:" in qa_raw_text:
        test_cmd = qa_raw_text.split("---TEST_COMMAND:")[1].split("---")[0].strip()

    if not test_cmd:
        print("⚠️ QA Agent forgot the test command. Spinning up Fallback Micro-Agent...")
        fallback_prompt = f"Repo structure:\n{repo_tree}\nWhat is the standard, single-line terminal command to install testing dependencies and run tests with coverage? Respond ONLY with the raw bash command."
        test_cmd = call_llm(fallback_prompt, temperature=0.0, timeout=60)

    return test_cmd

def run_reviewer_agent(ticket_id: str, jira_context: str, diff_text: str):
    print("🧐 Senior Reviewer Agent is analyzing logic and scope...")
    reviewer_prompt = f"""
    You are a strict Expert Senior Code Reviewer and Tech Lead for ticket {ticket_id}.
    
    JIRA TICKET REQUIREMENTS:
    {jira_context}
    
    Review these code diffs generated by a developer:
    {diff_text}
    
    INSTRUCTIONS:
    1. Verify Completeness: Does the code implement EVERY requirement listed in the Jira ticket?
    2. Verify Scope (No Scope Creep): Does the code stay strictly within the boundaries of the ticket? Flag any unnecessary features or unrelated changes.
    3. Verify Quality: Look for logic bugs, security flaws, unoptimized code, and bad practices.
    
    - If the code fully satisfies the ticket, has no scope creep, and is structurally sound, respond with EXACTLY: APPROVED
    - If there are missing features, scope creep, or bugs, provide a strict, numbered list of required fixes for the developer.
    """
    review_text = call_llm(reviewer_prompt, temperature=0.2)
    return "APPROVED" in review_text.upper(), review_text