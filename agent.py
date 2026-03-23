import os
import sys
import subprocess
import ollama
from jira import JIRA
from dotenv import load_dotenv

load_dotenv()

class VibeCoderAgent:
    def __init__(self, ticket_id):
        self.ticket_id = ticket_id
        self.token = os.getenv("GITHUB_TOKEN")
        self.repo_path = os.getenv("GITHUB_REPO")
        
        self.jira_url = os.getenv("JIRA_INSTANCE_URL")
        self.jira_user = os.getenv("JIRA_USER_EMAIL")
        self.jira_token = os.getenv("JIRA_API_TOKEN")

        self.jira = JIRA(server=self.jira_url, basic_auth=(self.jira_user, self.jira_token))
        
        # Ensure you have pulled this exact model via `ollama pull qwen2.5-coder:7b`
        self.model_name = os.getenv("OLLAMA_MODEL")
        
        self.branch_name = f"feat-{ticket_id.lower()}"
        self.remote_url = f"https://x-access-token:{self.token}@github.com/{self.repo_path}.git"

    def run_shell(self, cmd, timeout=30):
        """Execute terminal commands safely with a timeout for blocking processes."""
        print(f"💻 Running: {cmd[:60]}...") 
        try:
            # We use timeout to kill processes like 'npm run dev' that run forever
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode != 0:
                return False, result.stderr.strip()
            return True, result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            print(f"⚠️ Command timed out after {timeout}s. (Expected if it's a dev server).")
            return True, "Process timed out (likely a background server)."

    def get_repo_context(self):
        """Scans the local directory to give the LLM structural context."""
        ignore_dirs = {'.git', 'node_modules', '__pycache__', 'dist', 'build', '.venv'}
        tree = []
        
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            level = root.replace(".", "").count(os.sep)
            indent = " " * 4 * (level)
            tree.append(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 4 * (level + 1)
            for f in files:
                tree.append(f"{subindent}{f}")
                
        # Limit to first 200 lines to prevent blowing up the context window on huge repos
        return "\n".join(tree[:200])

    def generate_and_parse(self, prompt, attempt=1):
        """Handles talking to Ollama and extracting files/commands."""
        print(f"🧠 Local LLM is architecting (Attempt {attempt})...")
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={"temperature": 0.1, "num_ctx": 8192}
            )
            raw_text = response.get('response', '')
        except Exception as e:
            return None, [], f"Ollama Error: {e}"

        # Parse Files
        verified_files = []
        if "---FILE:" in raw_text:
            parts = raw_text.split("---FILE:")
            for part in parts[1:]:
                if "---" not in part or "---END---" not in part:
                    continue
                path = part.split("---")[0].strip().strip("`'\" \n")
                content = part.split("---")[1].split("---END---")[0].strip()
                
                if os.path.dirname(path):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                
                if os.path.exists(path):
                    verified_files.append(path)

        # Parse Commands
        commands_to_run = []
        if "---CMD:" in raw_text:
            cmd_parts = raw_text.split("---CMD:")
            for part in cmd_parts[1:]:
                clean_cmd = part.split("---")[0].strip().replace("`", "")
                if clean_cmd:
                    commands_to_run.append(clean_cmd)

        return verified_files, commands_to_run, None

    def execute(self):
        # 1. Fetch Jira Context
        print(f"🔍 Fetching Jira ticket {self.ticket_id}...")
        try:
            issue = self.jira.issue(self.ticket_id)
            jira_context = f"Summary: {issue.fields.summary}\nDetails: {issue.fields.description}"
        except Exception as e:
            print(f"❌ Failed to fetch Jira ticket: {e}")
            return

        # 2. Local Git Setup
        print("🔄 Preparing git branch...")
        self.run_shell("git checkout main")
        self.run_shell("git pull origin main")
        
        success, check_branch = self.run_shell(f"git rev-parse --verify {self.branch_name}")
        if not success: # Branch doesn't exist
            self.run_shell(f"git checkout -b {self.branch_name}")
        else:
            self.run_shell(f"git checkout {self.branch_name}")

        # 3. Read Codebase
        repo_tree = self.get_repo_context()

        # 4. Initial Prompt Build
        base_prompt = f"""
        You are a Senior Software Engineer.
        
        JIRA TICKET:
        {jira_context}
        
        CURRENT REPOSITORY STRUCTURE:
        {repo_tree}
        
        INSTRUCTIONS:
        1. For files to create/modify, respond ONLY in this format:
        ---FILE: path/to/file.ext---
        content
        ---END---
        
        2. To execute necessary system commands (e.g., npm install), use:
        ---CMD: your terminal command---
        
        Ensure file paths match the existing repository structure.
        """

        current_prompt = base_prompt
        max_retries = 2
        
        # 5. The Self-Healing Loop
        for attempt in range(1, max_retries + 2):
            files, commands, err = self.generate_and_parse(current_prompt, attempt)
            
            if err:
                print(f"❌ {err}")
                break
                
            if not files and not commands:
                print("🛑 AI returned no valid files or commands.")
                break

            print(f"   ✅ Saved {len(files)} files to disk.")

            # Execute Commands safely
            execution_failed = False
            failed_error = ""
            
            if commands:
                chained_command = " && ".join(commands)
                print(f"🚀 Auto-Executing sequence: {chained_command}")
                
                success, output = self.run_shell(chained_command)
                
                if not success:
                    print(f"❌ Command Failed:\n{output}")
                    execution_failed = True
                    failed_error = output
                else:
                    print(f"✅ Commands Succeeded.")

            # Self-Healing Evaluation
            if execution_failed and attempt <= max_retries:
                print("🩹 Initiating AI Self-Healing...")
                current_prompt = f"""
                You previously attempted to solve a ticket, but your terminal command failed.
                
                FAILED COMMAND: {chained_command}
                ERROR OUTPUT: {failed_error}
                
                Please fix the error by outputting the corrected ---FILE:--- contents or new ---CMD:--- instructions.
                """
            elif execution_failed:
                print("🛑 Max retries reached. Moving to Git Push anyway.")
                break
            else:
                # Everything worked! Break the loop.
                break

        # 6. Git Push
        print("\n🚀 Preparing to push to GitHub...")
        self.run_shell("git add .")
        success, git_status = self.run_shell("git status --porcelain")
        
        if not git_status:
            print("🛑 Git reports no changes. Aborting push.")
            return
            
        print("✅ Git detected changes. Committing and pushing...")
        self.run_shell(f"git commit -m 'Auto-implementation of {self.ticket_id}'")
        self.run_shell(f"git push --set-upstream origin {self.branch_name}")

        print(f"\n✨ MISSION COMPLETE!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 agent.py <JIRA_TICKET_ID>")
    else:
        agent = VibeCoderAgent(sys.argv[1])
        agent.execute()