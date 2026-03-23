import os
import sys
import subprocess
import ollama  # Switched from google.genai
from jira import JIRA
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

class VibeCoderAgent:
    def __init__(self, ticket_id):
        self.ticket_id = ticket_id
        # Credentials
        self.token = os.getenv("GITHUB_TOKEN")
        self.repo_path = os.getenv("GITHUB_REPO")
        
        # Jira Config
        self.jira_url = os.getenv("JIRA_INSTANCE_URL")
        self.jira_user = os.getenv("JIRA_USER_EMAIL")
        self.jira_token = os.getenv("JIRA_API_TOKEN")

        # Initialize Jira
        self.jira = JIRA(server=self.jira_url, basic_auth=(self.jira_user, self.jira_token))
        
        # Local LLM Config
        # Using qwen2.5-coder for superior logic and code generation
        self.model_name = os.getenv("OLLAMA_MODEL")
        
        # Logic for Isolation
        self.branch_name = f"feat-{ticket_id.lower()}"
        self.remote_url = f"https://x-access-token:{self.token}@github.com/{self.repo_path}.git"

    def run_shell(self, cmd):
        """Execute terminal commands and return output."""
        print(f"💻 Running: {cmd[:50]}...") 
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️ Git/Shell Note: {result.stderr.strip()}")
        return result.stdout.strip()

    def execute(self):
        # 1. Fetch Jira Context
        print(f"🔍 Fetching Jira ticket {self.ticket_id}...")
        issue = self.jira.issue(self.ticket_id)
        context = f"Summary: {issue.fields.summary}\nDetails: {issue.fields.description}"

        # 2. Local Git Setup
        print("🔄 Isolating local git for this repo...")
        self.run_shell(f"git remote set-url origin {self.remote_url}")
        self.run_shell("git checkout main")
        self.run_shell("git pull origin main")
        self.run_shell(f"git checkout -b {self.branch_name}")

        # 3. AI Reasoning (Local via Ollama)
        print(f"🧠 Local LLM ({self.model_name}) is architecting...")
        prompt = f"""
        You are a Senior Software Engineer.
        TASK: {context}
        
        Respond ONLY with a list of files to create/modify in this exact format:
        ---FILE: path/to/file.ext---
        content
        ---END---
        
        Include all necessary project files (HTML, JS, CSS, README, etc.) to complete the task.
        Do not include conversational text or explanations outside the tags.
        """
        
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    "temperature": 0.2, # Lower temperature for better structural adherence
                    "num_ctx": 8192      # Larger context window for coding tasks
                }
            )
            raw_text = response['response']
        except Exception as e:
            print(f"❌ Ollama Error: {e}")
            return

        # 4. Physical File Creation
        print("📝 Writing files to local disk...")
        parts = raw_text.split("---FILE: ")
        for part in parts[1:]:
            try:
                # Splitting the tag logic
                header_split = part.split("---")
                path = header_split[0].strip()
                
                content_split = header_split[1].split("---END---")
                content = content_split[0].strip()
                
                # Create directories if they don't exist
                os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
                
                with open(path, "w") as f:
                    f.write(content)
                print(f"   ✅ Created: {path}")
            except Exception as e:
                print(f"   ❌ Failed to write {path}: {e}")

        # 5. Git Push
        print("🚀 Pushing to GitHub...")
        self.run_shell("git add .")
        self.run_shell(f"git commit -m 'Auto-implementation of {self.ticket_id}'")
        self.run_shell(f"git push --set-upstream origin {self.branch_name}")

        print(f"\n✨ MISSION COMPLETE!")
        print(f"Check your VS Code sidebar to see the new files.")
        print(f"Check GitHub for the new branch: {self.branch_name}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 agent.py <JIRA_TICKET_ID>")
    else:
        agent = VibeCoderAgent(sys.argv[1])
        agent.execute()