import os
import json
import ollama
import concurrent.futures

def call_llm(prompt: str, format_type=None, temperature=0.1, model="qwen2.5-coder:7b", timeout=180):
    """
    Standardized wrapper for all Ollama LLM requests.
    Enforces a strict compute timeout to prevent local models from getting stuck 
    in infinite token generation loops, hanging the server indefinitely.
    """
    options = {"temperature": temperature, "num_ctx": 8192}
    
    def _generate():
        return ollama.generate(model=model, prompt=prompt, format=format_type, options=options)
        
    try:
        # Wrap the execution in a separate thread so we can impose a hard kill-switch via timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_generate)
            response = future.result(timeout=timeout) 
            
        raw = response.get("response", "").strip()
        
        # Clean up stray Markdown code blocks if the model hallucinates them at the top level
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]).strip()
            
        if not raw: raise ValueError("Model returned empty string.")
        return raw
        
    except concurrent.futures.TimeoutError:
        raise ValueError(f"LLM Generation timed out after {timeout} seconds. The model got stuck.")
    except Exception as e:
        raise ValueError(f"LLM Error: {str(e)}")

def extract_and_save_files(raw_text: str, repo_path: str, saved_files: list):
    """
    Parses the custom `---FILE: path---` delimiting format.
    Includes critical protections against Path Traversal vulnerabilities and partial generations.
    """
    if "---FILE:" not in raw_text: 
        return
        
    parts = raw_text.split("---FILE:")
    for part in parts[1:]:
        if not part.strip(): continue
        
        # Guard: Ensure the model actually finished writing the file
        if "---END---" not in part:
            raise ValueError("LLM generation was truncated before completion. Try writing more concise code or increase max tokens.")
            
        raw_path = part.split("---")[0].strip().strip("`'\" \n")
        content = part.split("---")[1].split("---END---")[0].strip()
        
        # Guard: Path Traversal Security check
        # Resolves relative paths (like `../`) and asserts they remain strictly inside the target repo
        full_path = os.path.abspath(os.path.join(repo_path, raw_path))
        repo_abs_path = os.path.abspath(repo_path)
        
        if not full_path.startswith(repo_abs_path):
            raise ValueError(f"Security Alert: Agent attempted Path Traversal outside workspace directory: {raw_path}")
            
        # Strip rogue markdown wrappers that corrupt source code compilation
        if content.startswith("```"):
            first_newline_idx = content.find("\n")
            if first_newline_idx != -1:
                content = content[first_newline_idx+1:]
        if content.endswith("```"):
            content = content[:-3].strip()
        
        # Write to disk safely
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f: 
            f.write(content.strip() + "\n")
            
        if raw_path not in saved_files: 
            saved_files.append(raw_path)

# ------------------------------------------------------------------
# THE 4 SPECIALIZED AI AGENTS
# ------------------------------------------------------------------

def generate_architect_plan(ticket_id: str, jira_context: str, repo_tree: str, feedback: str = None, previous_plan: dict = None):
    """
    The Architect Agent. Generates strict JSON defining the architectural 
    approach, the required CLI commands to set the project up, and the files to mutate.
    """
    prompt = f"You are an expert AI Software Architect.\nJIRA TICKET ({ticket_id}):\n{jira_context}\nCURRENT REPOSITORY STRUCTURE:\n{repo_tree}\n"
    
    if feedback and previous_plan:
        prompt += f"PREVIOUS PLAN:\n{json.dumps(previous_plan, indent=2)}\nUSER FEEDBACK:\n{feedback}\nRevise the plan based STRICTLY on the feedback.\n"
    else:
        prompt += "Analyze the ticket and repository, and output a strict JSON plan.\n"

    # Explicit schema definition and anti-laziness rules to prevent empty setups or dummy commands
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
    5. DIRECTORY MATCHING: You MUST inspect the CURRENT REPOSITORY STRUCTURE. 
       - Do NOT invent new root folders. If a `src` or `components` folder already exists, you MUST place new files inside the EXISTING folders.
       - NEVER create duplicate structures like `src/src/`.
       - If adding a feature to an existing app, modify the EXISTING entry points (e.g., `src/App.jsx`, `src/main.jsx`) in `files_to_modify` rather than creating new ones.
    """
    print("🧠 Architect Agent is planning...")
    return json.loads(call_llm(prompt, format_type="json"))

def run_developer_agent(prompt: str, repo_path: str, saved_files: list):
    """The Developer Agent. Executes the Architect's plan and outputs raw source code."""
    print("💻 Developer Agent is writing implementation code...")
    raw_text = call_llm(prompt)
    extract_and_save_files(raw_text, repo_path, saved_files)

def run_qa_agent(saved_files: list, repo_tree: str, repo_path: str):
    """
    The QA Agent. Determines the language framework contextually and writes unit tests,
    but no longer attempts to execute them locally.
    """
    print("🧪 QA Engineer Agent is writing unit tests...")
    
    qa_prompt = f"""
    You are the QA Automation Engineer. Modified files: {saved_files}.
    CURRENT REPOSITORY STRUCTURE:\n{repo_tree}
    
    INSTRUCTIONS:
    1. Write comprehensive unit tests for the newly modified or created code.
    2. Identify the testing framework from the repository tree (e.g., Jest/Vitest for React, PyTest for Python, JUnit for Java) and write tests matching that syntax.
    3. TEST DISCOVERY: Ensure your generated test file uses standard naming conventions so a test runner can find it later (e.g., appending `.test.jsx`, `.spec.ts`, or prefixing `test_`).
    
    Respond EXACTLY in this format. DO NOT use markdown code blocks (```) inside the file content.
    ---FILE: path/to/test_file.ext---
    // raw test code here
    ---END---
    """
    qa_raw_text = call_llm(qa_prompt)
    extract_and_save_files(qa_raw_text, repo_path, saved_files)

def run_reviewer_agent(ticket_id: str, jira_context: str, repo_tree: str, diff_text: str):
    """
    The Senior Tech Lead Agent. Performs deep static analysis on the generated code,
    checking folder structure, linting, DRY principles, and Jira scope alignment.
    """
    print("🧐 Senior Reviewer Agent is performing deep static analysis...")
    
    reviewer_prompt = f"""
    You are the Senior Staff Software Engineer and Tech Lead. 
    A developer has just submitted code to resolve the following Jira Ticket:
    TICKET ({ticket_id}):\n{jira_context}
    
    CURRENT REPOSITORY STRUCTURE:
    {repo_tree}
    
    SUBMITTED FILES (NEW CODE / DIFFS):
    {diff_text}
    
    INSTRUCTIONS:
    Perform a DEEP, ruthless static analysis of the submitted code. Evaluate the submission against these 5 pillars:
    
    1. FOLDER STRUCTURE & ARCHITECTURE: Cross-reference the file paths in the SUBMITTED FILES with the CURRENT REPOSITORY STRUCTURE. Did they put the files in the correct place? Did they hallucinate a nested folder (like `src/src/` or `app/app/`)?
    2. DRY PRINCIPLES & REPETITION: Is there duplicated logic? Could they have reused an existing component or utility?
    3. LINTING & IMPORTS: Scan the code for missing imports (e.g., React, useState, or external libraries). Are there obvious typos, unused variables, or syntax errors?
    4. SCOPE CREEP: Does the code strictly solve the Jira ticket without adding unnecessary "gold-plating" or unrelated features?
    5. TEST VALIDITY: If test files are included, do they actually test the core logic, or are they just dummy assertions (like `expect(1).toBe(1)` or `pass`)?
    
    YOUR DECISION:
    If the code passes ALL checks, respond with EXACTLY the word "APPROVED" on the very first line, followed by a brief summary.
    If the code fails ANY critical check, respond with EXACTLY the word "REJECTED" on the very first line, followed by a detailed, numbered list of actionable fixes the developer must implement.
    
    *Note: Be strict on architecture, bugs, and missing imports, but do not reject for minor stylistic preferences (like single vs. double quotes).*
    """
    
    review_output = call_llm(reviewer_prompt)
    
    # Parse the strict approval/rejection flag safely
    is_approved = review_output.strip().upper().startswith("APPROVED")
    
    return is_approved, review_output