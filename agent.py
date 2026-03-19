import os
import sys
import base64
from jira import JIRA
from github import Github, Auth, InputGitTreeElement
from google import genai
from dotenv import load_dotenv

load_dotenv()

class ArchitectAgent:
    def __init__(self, ticket_id):
        self.ticket_id = ticket_id
        # Credentials
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.repo_name = os.getenv("GITHUB_REPO")
        
        # Setup APIs
        auth = Auth.Token(self.github_token)
        self.github = Github(auth=auth)
        self.repo = self.github.get_repo(self.repo_name)
        self.jira = JIRA(server=os.getenv("JIRA_INSTANCE_URL"), 
                         basic_auth=(os.getenv("JIRA_USER_EMAIL"), os.getenv("JIRA_API_TOKEN")))
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.branch_name = f"feat-{ticket_id.lower()}"

    def execute(self):
        # 1. Fetch Jira Ticket
        issue = self.jira.issue(self.ticket_id)
        context = f"Ticket: {issue.fields.summary}\nDetails: {issue.fields.description}"
        
        # 2. Gemini Project Architecture
        prompt = f"""
        You are an AI Software Engineer.
        TASK: {context}
        
        Generate the code for this project. 
        Return your answer as a list of files and their content in this format:
        ---FILE: path/to/file.ext---
        content here
        ---END---
        """
        
        print(f"🧠 LLM is architecting {self.ticket_id}...")
        response = self.client.models.generate_content(model=os.getenv("LLM_MODEL"), contents=prompt).text

        # 3. Parse Files
        files_to_upload = []
        parts = response.split("---FILE: ")
        for part in parts[1:]:
            path = part.split("---")[0].strip()
            content = part.split("---")[1].split("---END---")[0].strip()
            files_to_upload.append({"path": path, "content": content})

        if not files_to_upload:
            print("❌ No files generated. Check Gemini's response.")
            return

        # 4. Push to GitHub using API (No local Git CLI)
        print(f"🚀 Pushing {len(files_to_upload)} files to GitHub via API...")
        
        try:
            # Get main branch SHA to branch from
            main_branch = self.repo.get_branch("main")
            base_sha = main_branch.commit.sha
            
            # Create a new branch
            self.repo.create_git_ref(ref=f"refs/heads/{self.branch_name}", sha=base_sha)
            
            # Create a list of elements for the Git Tree
            elements = []
            for f in files_to_upload:
                element = InputGitTreeElement(path=f['path'], mode='100644', type='blob', content=f['content'])
                elements.append(element)
            
            # Create the tree and commit
            base_tree = self.repo.get_git_tree(sha=base_sha)
            tree = self.repo.create_git_tree(elements, base_tree)
            parent = self.repo.get_git_commit(sha=base_sha)
            commit = self.repo.create_git_commit(f"Auto-implementation of {self.ticket_id}", tree, [parent])
            
            # Update the branch reference
            branch_ref = self.repo.get_git_ref(f"heads/{self.branch_name}")
            branch_ref.edit(sha=commit.sha)

            # 5. Create PR
            pr = self.repo.create_pull(
                title=f"Implementation: {self.ticket_id}",
                body=f"Agent completed {self.ticket_id}.\n\n{context}",
                head=self.branch_name,
                base="main"
            )
            print(f"✅ Success! PR opened at: {pr.html_url}")

        except Exception as e:
            print(f"💥 GitHub API Error: {e}")

if __name__ == "__main__":
    agent = ArchitectAgent(sys.argv[1])
    agent.execute()