import os
import shutil
import subprocess
import uuid
import requests
from urllib.parse import urlparse
import time

class WorkspaceManager:
    """
    Manages the local file system and Git operations for a specific repository.
    Acts as the bridge between the AI agents and the actual codebase.
    """
    
    def __init__(self, repo_url: str, github_token: str, base_dir: str = "workspaces"):
        """Initializes the workspace manager and calculates the local clone path."""
        self.repo_url = repo_url
        self.github_token = github_token
        self.base_dir = os.path.abspath(base_dir)
        
        # Parse the repo URL to generate a local folder name (e.g., 'username/repo' -> 'repo')
        parsed_url = urlparse(self.repo_url)
        self.repo_name = parsed_url.path.strip("/").split("/")[-1].replace(".git", "")
        self.repo_path = os.path.join(self.base_dir, self.repo_name)

    def _get_auth_url(self) -> str:
        """Constructs a securely authenticated GitHub URL using the provided Personal Access Token (PAT)."""
        url = self.repo_url if self.repo_url.endswith(".git") else self.repo_url + ".git"
        parsed = urlparse(url)
        return f"{parsed.scheme}://x-access-token:{self.github_token}@{parsed.netloc}{parsed.path}"

    def verify_access(self):
        """Verifies if the provided GitHub token has access to the repository using ls-remote."""
        try:
            subprocess.run(["git", "ls-remote", self._get_auth_url()], check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def setup_workspace(self):
        """
        Prepares the local environment. If the repo already exists locally, it deletes it 
        to ensure a completely fresh state, then clones it from GitHub.
        """
        os.makedirs(self.base_dir, exist_ok=True)
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path, ignore_errors=True)
                
        subprocess.run(["git", "clone", self._get_auth_url(), self.repo_path], check=True, capture_output=True, text=True)
        
        # Set a generic local Git identity so commits don't crash on headless deployment servers
        self.run_git_command("config", "user.name", "VibeCoder AI")
        self.run_git_command("config", "user.email", "bot@vibecoder.ai")
        
        return self.repo_path

    def run_git_command(self, *args, check=True):
        """
        Wrapper for executing Git CLI commands inside the cloned repository.
        Masks the GitHub token in terminal logs for security.
        """
        cmd = ["git"] + list(args)
        print(f"💻 Git: {' '.join(cmd).replace(self.github_token, '***')}")
        return subprocess.run(
            cmd, cwd=self.repo_path if os.path.exists(self.repo_path) else None,
            check=check, capture_output=True, text=True
        )

    def get_repo_tree(self, max_lines=200, max_depth=3):
        """
        Generates a text-based directory tree to feed into the LLM context.
        Uses aggressive pruning (ignoring node_modules, .git, etc.) and strict depth/line 
        limits to prevent blowing out the LLM's token window.
        """
        ignore_dirs = {'.git', 'node_modules', '__pycache__', 'dist', 'build', '.venv', '.agent', '.idea', '.vscode'}
        tree = []
        for root, dirs, files in os.walk(self.repo_path):
            # Prune ignored directories immediately
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            
            level = root.replace(self.repo_path, "").count(os.sep)
            
            # Stop diving deeper if we hit our depth limit
            if level > max_depth:
                dirs[:] = [] 
                continue
                
            indent = " " * 4 * level
            
            # Render the root folder as '.' instead of the literal repo name
            if root == self.repo_path:
                tree.append(f"{indent}.")
            else:
                tree.append(f"{indent}{os.path.basename(root)}/")
                
            for f in files: 
                if not f.endswith(('.pyc', '.log', '.lock')):
                    tree.append(f"{' ' * 4 * (level + 1)}{f}")
                    
            # Hard stop if the tree is getting too long for the LLM context
            if len(tree) >= max_lines:
                tree.append(f"{' ' * 4 * level}... (Truncated for context size)")
                break
                
        return "\n".join(tree[:max_lines + 1])

    def get_available_branches(self):
        """Fetches all remote branches and returns a cleaned, sorted list for the UI dropdown."""
        # Use check=False so it doesn't crash if the repo is completely empty
        self.run_git_command("fetch", "--all", check=False)
        result = self.run_git_command("branch", "-a", check=False)
        
        branches = set()
        if result.returncode == 0:
            branches = {line.replace('* ', '').replace('remotes/origin/', '').strip() 
                        for line in result.stdout.split('\n') if line.strip() and '->' not in line}
            
        # Empty repository initialization
        if not branches:
            print("🌱 Empty repository detected. Initializing 'main' branch with README...")
            
            self.run_git_command("checkout", "-b", "main", check=False)
            readme_path = os.path.join(self.repo_path, "README.md")
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(f"# {self.repo_name}\n\nRepository initialized by VibeCoder AI.")
            
            self.run_git_command("add", "README.md", check=False)
            self.run_git_command("commit", "-m", "Initial commit", check=False)
            auth_url = self._get_auth_url()
            self.run_git_command("remote", "set-url", "origin", auth_url, check=False)
            push_res = self.run_git_command("push", "-u", "origin", "main", check=False)
            
            if push_res.returncode != 0:
                print(f"❌ FAILED TO PUSH INITIAL COMMIT:\n{push_res.stderr}")
                raise ValueError("Could not push to GitHub. Check your Personal Access Token permissions (it needs 'repo' scope).")
            else:
                print("✅ Successfully initialized and pushed 'main' to GitHub!")
            
            return ["main"]
            
        branch_list = sorted(list(branches))
        
        # Ensure main/master is always at the top of the dropdown list
        if "main" in branch_list: 
            branch_list.insert(0, branch_list.pop(branch_list.index("main")))
        elif "master" in branch_list: 
            branch_list.insert(0, branch_list.pop(branch_list.index("master")))
            
        return branch_list

    def checkout_base_branch(self, branch_name: str):
        """Checks out the selected base branch and pulls the latest changes."""
        self.run_git_command("checkout", branch_name)
        self.run_git_command("pull", "origin", branch_name)
        return branch_name

    def setup_branch(self, ticket_id: str, base_branch: str = "main"):
        """Creates a unique feature branch for the AI to work on (e.g., feature/KAN-123-a1b2c3)."""
        branch_name = f"feature/{ticket_id.upper()}-{uuid.uuid4().hex[:6]}"
        self.run_git_command("checkout", base_branch)
        self.run_git_command("pull", "origin", base_branch)
        self.run_git_command("checkout", "-b", branch_name)
        return branch_name

    def get_file_diffs(self, modified_files: list):
        """
        Extracts the original file content from Git HEAD and pairs it with the newly 
        AI-generated content. Used by the UI Diff Viewer and the Reviewer Agent.
        """
        diffs = []
        for file_path in modified_files:
            old_result = self.run_git_command("show", f"HEAD:{file_path}", check=False)
            old_content = old_result.stdout if old_result.returncode == 0 else ""

            full_path = os.path.join(self.repo_path, file_path)
            new_content = open(full_path, "r", encoding="utf-8").read() if os.path.exists(full_path) else ""
            diffs.append({"file": file_path, "old_content": old_content, "new_content": new_content})
        return diffs

    def ensure_gitignore(self):
        """
        Ensures standard heavy/junk directories (like node_modules and .agent) 
        are ignored so the AI doesn't accidentally commit them.
        """
        gitignore_path = os.path.join(self.repo_path, ".gitignore")
        ignore_rules = ["node_modules/", "dist/", "build/", ".env", "__pycache__/", ".DS_Store", ".agent/"]
        
        # Create fresh if it doesn't exist
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write("\n".join(ignore_rules) + "\n")
            return

        # Otherwise, append missing rules gracefully
        with open(gitignore_path, "r", encoding="utf-8") as f:
            existing_rules = f.read().splitlines()

        missing_rules = [rule for rule in ignore_rules if rule not in existing_rules]
        if missing_rules:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n# VibeCoder Auto-Ignores\n" + "\n".join(missing_rules) + "\n")

    def create_pull_request(self, target_branch: str, base_branch: str, title: str, body: str):
        """Uses the GitHub API to open a Pull Request from the AI's feature branch."""
        print(f"📝 Opening Pull Request: {target_branch} -> {base_branch}")
        owner_repo = self.repo_url.replace("https://github.com/", "").replace(".git", "")
        url = f"https://api.github.com/repos/{owner_repo}/pulls"
        headers = {"Authorization": f"Bearer {self.github_token}", "Accept": "application/vnd.github.v3+json"}
        data = {"title": title, "head": target_branch, "base": base_branch, "body": body}
        
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 201: 
            return response.json().get("html_url")
        print(f"⚠️ PR Creation Failed: {response.text}")
        return None
    
    def create_testing_branch(self, current_branch: str):
        """Creates a dedicated testing branch off the current feature branch."""
        test_branch = f"{current_branch}-testing"
        self.run_git_command("checkout", "-b", test_branch)
        return test_branch

    def wait_for_ci_and_get_logs(self, branch_name: str, timeout_seconds: int = 600) -> dict:
        """
        Polls the GitHub REST API to check the status of GitHub Actions for the pushed branch.
        Returns a dict with 'success' boolean and 'logs' string if it failed.
        """
        print(f"☁️ Waiting for GitHub Actions CI to finish on branch '{branch_name}'...")
        
        # Extract owner/repo from the github URL 
        parsed = urlparse(self.repo_url)
        repo_path = parsed.path.strip("/").replace(".git", "")
        base_api_url = f"https://api.github.com/repos/{repo_path}/actions/runs"
        
        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        start_time = time.time()
        
        # Give GitHub a few seconds to register the push and trigger the action
        time.sleep(10)

        while (time.time() - start_time) < timeout_seconds:
            try:
                response = requests.get(f"{base_api_url}?branch={branch_name}", headers=headers)
                
                if response.status_code != 200:
                    print(f"⚠️ Failed to fetch CI status (HTTP {response.status_code}). Assuming success to prevent hanging.")
                    return {"success": True, "logs": ""}

                runs = response.json().get("workflow_runs", [])
                if not runs:
                    time.sleep(15)
                    continue

                # Get the most recent run for this branch
                latest_run = runs[0]
                status = latest_run.get("status")
                conclusion = latest_run.get("conclusion")

                if status == "completed":
                    if conclusion == "success":
                        print("✅ GitHub Actions CI Passed!")
                        return {"success": True, "logs": ""}
                    else:
                        print("❌ GitHub Actions CI Failed! Fetching logs for self-healing...")
                        
                        # Fetch the jobs for this run to pinpoint what failed
                        jobs_url = latest_run.get("jobs_url")
                        jobs_response = requests.get(jobs_url, headers=headers).json()
                        
                        failed_logs = f"Remote CI Pipeline Failed (Conclusion: {conclusion}).\n"
                        for job in jobs_response.get("jobs", []):
                            if job.get("conclusion") == "failure":
                                failed_logs += f"\nFailed Job: {job.get('name')}\n"
                                for step in job.get("steps", []):
                                    if step.get("conclusion") == "failure":
                                        failed_logs += f"Failed Step: {step.get('name')}\n"
                        
                        return {"success": False, "logs": failed_logs}
                
                # If still queued or in_progress, wait 15 seconds and check again
                print(f"⏳ CI Status: {status}... waiting 15 seconds.")
                time.sleep(15)
                
            except Exception as e:
                print(f"⚠️ Error polling GitHub API: {str(e)}")
                return {"success": True, "logs": ""}
            
        print("⚠️ CI Polling timed out. Proceeding pipeline.")
        return {"success": True, "logs": "Timeout"}