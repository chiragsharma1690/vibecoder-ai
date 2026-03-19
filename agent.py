import os
import sys
import subprocess
from jira import JIRA
from google import genai
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

class VibeCoderAgent:
    def __init__(self, ticket_id):
        self.ticket_id = ticket_id
        # Credentials
        self.token = os.getenv("GITHUB_TOKEN")
        self.repo_path = os.getenv("GITHUB_REPO") # e.g., "username/repo"
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        
        # Jira Config
        self.jira_url = os.getenv("JIRA_INSTANCE_URL")
        self.jira_user = os.getenv("JIRA_USER_EMAIL")
        self.jira_token = os.getenv("JIRA_API_TOKEN")

        # Initialize APIs
        self.jira = JIRA(server=self.jira_url, basic_auth=(self.jira_user, self.jira_token))
        self.client = genai.Client(api_key=self.gemini_key)
        
        # Logic for Isolation
        self.branch_name = f"feat-{ticket_id.lower()}"
        self.remote_url = f"https://x-access-token:{self.token}@github.com/{self.repo_path}.git"

    def run_shell(self, cmd):
        """Execute terminal commands and return output."""
        print(f"💻 Running: {cmd[:50]}...") # Truncated for clean logs
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️ Git/Shell Note: {result.stderr.strip()}")
        return result.stdout.strip()

    def execute(self):
        # 1. Fetch Jira Context
        print(f"🔍 Fetching Jira ticket {self.ticket_id}...")
        issue = self.jira.issue(self.ticket_id)
        context = f"Summary: {issue.fields.summary}\nDetails: {issue.fields.description}"

        # 2. Local Git Setup (Account Isolation)
        print("🔄 Isolating local git for this repo...")
        self.run_shell(f"git remote set-url origin {self.remote_url}")
        self.run_shell("git checkout main || git checkout master")
        self.run_shell("git pull origin main || git pull origin master")
        self.run_shell(f"git checkout -b {self.branch_name}")

        # 3. AI Reasoning
        print("🧠 Gemini is architecting the solution...")
        prompt = f"""
        You are a Senior Software Engineer.
        TASK: {context}
        
        Respond ONLY with a list of files to create/modify in this exact format:
        ---FILE: path/to/file.ext---
        content
        ---END---
        
        Include all necessary project files (HTML, JS, CSS, README, etc.) to complete the task.
        """
        
        # response = self.client.models.generate_content(
        #     model=os.getenv("LLM_MODEL"), 
        #     contents=prompt
        # ).text

        # # 4. Physical File Creation (Visible in VS Code)
        # print("📝 Writing files to local disk...")
        # parts = response.split("---FILE: ")
        # for part in parts[1:]:
        #     try:
        #         path = part.split("---")[0].strip()
        #         content = part.split("---")[1].split("---END---")[0].strip()
                
        #         # Create directories if they don't exist
        #         os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
                
        #         with open(path, "w") as f:
        #             f.write(content)
        #         print(f"   ✅ Created: {path}")
        #     except Exception as e:
        #         print(f"   ❌ Failed to write {path}: {e}")

        # 5. Git Push & PR
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
