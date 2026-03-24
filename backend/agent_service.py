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

    prompt += """
    Do not include conversational text. You must respond ONLY with a valid JSON object matching this exact schema:
    {
        "strategy": "A 2-3 sentence explanation of how you will solve this.", 
        "files_to_modify": ["path/to/existing/file.ext"], 
        "new_files": ["path/to/new/file.ext"], 
        "commands_to_run": ["npm install x"], 
        "ui_components_to_screenshot": [
            {
                "route": "The exact URL path where the new/updated UI is visible (e.g., /, /settings, /profile)", 
                "selector": "The specific CSS selector of the modified component (e.g., #submit-btn, .nav-bar, body)"
            }
        ]
    }
    
    IMPORTANT INSTRUCTION: 
    The `ui_components_to_screenshot` array MUST be dynamically generated based on the actual UI components you are building or modifying for this specific Jira ticket. Do not use my placeholder examples. If no UI changes are being made (e.g., backend only), leave the array empty [].
    """

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
    developer_prompt = compile_developer_prompt(request.ticket_id, request.plan, session, workspace)
    max_attempts = 4 
    saved_files = []
    qa_passed = False
    qa_logs = []

    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 --- AGENT LOOP ATTEMPT {attempt} ---")
        
        # ---------------- 1. DEVELOPER AGENT ---------------- #
        print("💻 Developer Agent is writing implementation code...")
        try:
            response = ollama.generate(model="qwen2.5-coder:7b", prompt=developer_prompt, options={"temperature": 0.1, "num_ctx": 8192})
            raw_text = response.get("response", "")
        except Exception as e:
            raise ValueError(f"LLM Error: {str(e)}")

        if "---FILE:" in raw_text:
            parts = raw_text.split("---FILE:")
            for part in parts[1:]:
                if "---END---" not in part: continue
                path = part.split("---")[0].strip().strip("`'\" \n")
                content = part.split("---")[1].split("---END---")[0].strip()
                full_path = os.path.join(workspace.repo_path, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f: f.write(content)
                if path not in saved_files: saved_files.append(path)

        # Run Setup Commands
        if attempt == 1:
            commands = request.plan.get("commands_to_run", [])
            for cmd in commands: 
                if not cmd.strip(): continue
                workspace.run_shell_command(cmd)

        # ---------------- 2. QA ENGINEER AGENT (TEST GENERATION) ---------------- #
        print("🧪 QA Engineer Agent is analyzing the stack and writing unit tests...")
        
        # Give the QA agent the repo tree so it can infer the programming language
        qa_prompt = f"""
        You are the QA Automation Engineer. The Developer modified these files: {saved_files}.
        
        CURRENT REPOSITORY STRUCTURE:
        {workspace.get_repo_tree()}
        
        INSTRUCTIONS:
        1. Analyze the repository structure to determine the language and framework (e.g., Python, Node.js, Java, Go).
        2. Write unit tests for the modified code to ensure >80% coverage.
        3. Determine the correct testing framework for this stack (e.g., pytest for Python, jest for Node, JUnit for Java).
        4. Provide the exact terminal command to install dependencies (if needed) AND run the tests with a coverage report.
        5. Respond EXACTLY in this format:
        ---TEST_COMMAND: <your dynamic install & coverage command here>---
        ---FILE: path/to/test_file.ext---
        code
        ---END---
        """
        
        try:
            qa_response = ollama.generate(
                model="qwen2.5-coder:7b", 
                prompt=qa_prompt, 
                options={"temperature": 0.1, "num_ctx": 8192}
            )
            qa_raw_text = qa_response.get("response", "")
        except Exception as e:
            raise ValueError(f"QA LLM Error: {str(e)}")

        # Smart Dynamic Fallback for Test Commands
        test_cmd = ""
        if "---TEST_COMMAND:" in qa_raw_text:
            test_cmd = qa_raw_text.split("---TEST_COMMAND:")[1].split("---")[0].strip()

        # If the LLM forgets the command, infer it from the codebase files
        if not test_cmd:
            if os.path.exists(os.path.join(workspace.repo_path, "package.json")):
                test_cmd = "npm test -- --coverage"
            elif os.path.exists(os.path.join(workspace.repo_path, "requirements.txt")) or os.path.exists(os.path.join(workspace.repo_path, "pyproject.toml")):
                test_cmd = "pytest --cov=."
            elif os.path.exists(os.path.join(workspace.repo_path, "pom.xml")):
                test_cmd = "mvn clean test jacoco:report"
            elif os.path.exists(os.path.join(workspace.repo_path, "go.mod")):
                test_cmd = "go test -coverprofile=coverage.out ./..."
            else:
                test_cmd = "echo 'No standard package manager found to run tests.'"

        if "---FILE:" in qa_raw_text:
            parts = qa_raw_text.split("---FILE:")
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

        # ---------------- 3. QA EXECUTOR (TEST RUN & COVERAGE CHECK) ---------------- #
        qa_success, qa_output = workspace.run_qa_tests(test_cmd)
        qa_logs.append(f"QA Execution: {qa_output}")

        if not qa_success:
            print(f"❌ Tests failed or coverage < 80%. Self-healing...")
            if attempt < max_attempts:
                developer_prompt = f"The code or tests failed validation.\nTEST EXECUTION REPORT:\n{qa_output}\nFix the implementation OR the tests so that they pass with >80% coverage. Output the corrected files."
            continue

        print("🎉 QA Agent approved the tests! Passing to Reviewer...")

        # ---------------- 4. REVIEWER AGENT ---------------- #
        print("🧐 Senior Reviewer Agent is analyzing logic...")
        file_diffs = workspace.get_file_diffs(saved_files)
        diff_text = "".join([f"\n--- FILE: {d['file']} ---\nNEW CODE:\n{d['new_content']}\n" for d in file_diffs])

        reviewer_prompt = f"""
        You are a strict Expert Senior Code Reviewer. Review these diffs:
        {diff_text}
        - If the code is optimized, structurally sound, and safe, respond with exactly: APPROVED
        - If there are logic bugs or bad practices, provide a numbered list of fixes.
        """
        try:
            review_response = ollama.generate(model="qwen2.5-coder:7b", prompt=reviewer_prompt, options={"temperature": 0.2, "num_ctx": 8192})
            review_text = review_response.get("response", "").strip()
        except Exception as e:
            raise ValueError(f"Reviewer LLM Error: {str(e)}")

        if "APPROVED" in review_text.upper():
            print("✅ Senior Reviewer approved the code!")
            qa_passed = True
            break
        else:
            print("⚠️ Senior Reviewer requested changes. Self-healing...")
            if attempt < max_attempts:
                developer_prompt = f"The Senior Code Reviewer rejected your code.\nREVIEWER FEEDBACK:\n{review_text}\nFix the issues and output the corrected files."

    if not saved_files:
        raise ValueError("The Developer Agent failed to format the files correctly.")

    return saved_files, qa_passed, qa_logs

# ---------------- BACKGROUND WORKER (ASYNC MODE) ---------------- #
def background_agent_worker(request: ExecuteRequest, session: dict, workspace: WorkspaceManager):
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        saved_files, qa_passed, qa_logs = run_multi_agent_loop(request, session, workspace)

        workspace.ensure_gitignore()

        ui_components = request.plan.get("ui_components_to_screenshot", [{"route": "/", "selector": "body"}])
        screenshot_paths = workspace.capture_dev_screenshot(components=ui_components, port=5174)

        workspace.run_git_command("add", ".")
        workspace.run_git_command("commit", "-m", f"Auto-implemented {request.ticket_id}")
        workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
        
        owner_repo = workspace.repo_url.replace("https://github.com/", "").replace(".git", "")
        screenshots_md = "".join([f"![UI Preview](https://raw.githubusercontent.com/{owner_repo}/{branch_name}/{path})\n<br/>\n" for path in screenshot_paths])
        if not screenshots_md: screenshots_md = "*No screenshots captured.*"
        
        # 5. Attach the Coverage Report to the PR
        coverage_md = ""
        cov_path = os.path.join(workspace.repo_path, ".agent", "coverage.txt")
        if os.path.exists(cov_path):
            with open(cov_path, "r", encoding="utf-8") as f:
                # Grab the last 1500 characters of the report to keep the PR clean
                cov_text = f.read()[-1500:] 
            coverage_md = f"<details><summary>📊 Test Coverage Report (Click to expand)</summary>\n\n```text\n{cov_text}\n```\n</details>"
        
        pr_body = f"""### 🤖 VibeCoder AI Implementation
Resolves Jira Ticket: **{request.ticket_id}**

**Implementation Details:**
* Strategy: {request.plan.get('strategy', 'N/A')}
* Tests Passed: {'Yes ✅' if qa_passed else 'Failed / Skipped ⚠️'} 

{coverage_md}

**📸 Dev Environment Previews:**
{screenshots_md}
"""
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id} Implementation", pr_body)
        print(f"✨ ASYNC MISSION COMPLETE! PR: {pr_url}")
        
    except Exception as e:
        print(f"🔥 FATAL ERROR IN BACKGROUND AGENT WORKER: {str(e)}")
    """The heavy-lifting background task for Async Mode."""
    try:
        base_branch = session.get("base_branch", "main")
        branch_name = workspace.setup_branch(request.ticket_id, base_branch)
        
        # 1. Run the shared loop
        saved_files, qa_passed, qa_logs = run_multi_agent_loop(request, session, workspace)

        # 2. Prevent node_modules from being staged
        workspace.ensure_gitignore()

        # 3. TAKE SCREENSHOTS BEFORE COMMITTING!
        ui_components = request.plan.get("ui_components_to_screenshot", [{"route": "/", "selector": "body"}])
        screenshot_paths = workspace.capture_dev_screenshot(components=ui_components, port=5174)

        # 4. Git Operations
        workspace.run_git_command("add", ".")
        workspace.run_git_command("commit", "-m", f"Auto-implemented {request.ticket_id}")
        workspace.run_git_command("push", "--set-upstream", "origin", branch_name)
        
        # 5. Build the PR Body with multiple screenshots
        owner_repo = workspace.repo_url.replace("https://github.com/", "").replace(".git", "")
        
        screenshots_md = ""
        for path in screenshot_paths:
            raw_img_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch_name}/{path}"
            screenshots_md += f"![UI Preview]({raw_img_url})\n<br/>\n"
            
        if not screenshots_md:
            screenshots_md = "*No screenshots could be captured by the QA Agent.*"
        
        pr_body = f"""### 🤖 VibeCoder AI Implementation
Resolves Jira Ticket: **{request.ticket_id}**

**Implementation Details:**
* Strategy: {request.plan.get('strategy', 'N/A')}
* Tests Passed: {'Yes ✅' if qa_passed else 'Failed / Skipped ⚠️'} (Automated QA Agent)

**📸 Dev Environment Previews:**
{screenshots_md}

> *Note: These screenshots were auto-generated by Playwright during the QA phase.*
"""
        # 6. Open Pull Request
        pr_url = workspace.create_pull_request(branch_name, base_branch, f"Feature: {request.ticket_id} Implementation", pr_body)
        print(f"✨ ASYNC MISSION COMPLETE! PR: {pr_url}")
        
    except Exception as e:
        print(f"🔥 FATAL ERROR IN BACKGROUND AGENT WORKER: {str(e)}")