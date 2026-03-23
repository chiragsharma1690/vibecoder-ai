import os
import sys
import subprocess
import ollama
from jira import JIRA
from dotenv import load_dotenv

# Load credentials from .env
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

    def run_shell(self, cmd):
        """Execute terminal commands and return output."""
        print(f"💻 Running: {cmd[:60]}...") 
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0 and "already exists" not in result.stderr:
            print(f"⚠️ Git/Shell Note: {result.stderr.strip()}")
        return result.stdout.strip()

    def execute(self):
        # 1. Fetch Jira Context
        print(f"🔍 Fetching Jira ticket {self.ticket_id}...")
        try:
            issue = self.jira.issue(self.ticket_id)
            context = f"Summary: {issue.fields.summary}\nDetails: {issue.fields.description}"
        except Exception as e:
            print(f"❌ Failed to fetch Jira ticket: {e}")
            return

        # 2. Local Git Setup (Safe Branching)
        print("🔄 Preparing git branch...")
        self.run_shell("git checkout main")
        self.run_shell("git pull origin main")
        
        # Safely create or switch to the branch
        check_branch = self.run_shell(f"git rev-parse --verify {self.branch_name}")
        if not check_branch:
            self.run_shell(f"git checkout -b {self.branch_name}")
        else:
            self.run_shell(f"git checkout {self.branch_name}")

        # 3. AI Reasoning
        print(f"🧠 Local LLM ({self.model_name}) is architecting...")
        prompt = f"""
        You are a Senior Software Engineer.
        TASK: {context}
        
        Respond ONLY with a list of files to create/modify in this exact format:
        ---FILE: path/to/file.ext---
        content
        ---END---
        
        Do not include markdown code blocks around the format. Just the tags.
        """
        
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={"temperature": 0.1, "num_ctx": 8192}
            )
            raw_text = response.get('response', '')
        except Exception as e:
            print(f"❌ Ollama Error: {e}")
            return

        if "---FILE:" not in raw_text:
            print("❌ ERROR: LLM did not output the expected file format.")
            print(f"Raw Output Snippet: {raw_text[:200]}...")
            return

        # 4. Physical File Creation & Verification
        print("📝 Saving files to local disk...")
        parts = raw_text.split("---FILE:")
        verified_files = []

        for part in parts[1:]:
            try:
                if "---" not in part or "---END---" not in part:
                    continue
                    
                path_section = part.split("---")[0].strip()
                # Clean the path of any accidental backticks or quotes
                path = path_section.strip("`'\" \n")
                
                content = part.split("---")[1].split("---END---")[0].strip()
                
                # Create directories
                if os.path.dirname(path):
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                
                # Write to disk
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                
                # HARD VERIFICATION: Does the file actually exist on disk now?
                if os.path.exists(path):
                    print(f"   ✅ Successfully saved to disk: {path}")
                    verified_files.append(path)
                else:
                    print(f"   ❌ File write silently failed for: {path}")
                    
            except Exception as e:
                print(f"   ❌ Failed to parse/write file block: {e}")

        # 5. Git Push (Guarded by Disk & Status Checks)
        if not verified_files:
            print("🛑 No files were verified on the local disk. Aborting Git push.")
            return

        print("\n🚀 Preparing to push to GitHub...")
        self.run_shell("git add .")
        
        # Check if Git actually sees any changes
        git_status = self.run_shell("git status --porcelain")
        if not git_status:
            print("🛑 Git reports no changes. The files generated might be identical to existing ones, or saved outside the repo. Aborting push.")
            return
            
        print("✅ Git detected changes. Committing and pushing...")
        self.run_shell(f"git commit -m 'Auto-implementation of {self.ticket_id}'")
        self.run_shell(f"git push --set-upstream origin {self.branch_name}")

        print(f"\n✨ MISSION COMPLETE!")
        print(f"📂 Files created: {', '.join(verified_files)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 agent.py <JIRA_TICKET_ID>")
    else:
        agent = VibeCoderAgent(sys.argv[1])
        agent.execute()