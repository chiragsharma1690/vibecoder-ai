import os
import shutil
import subprocess
import uuid
import requests
import time
from urllib.parse import urlparse

from app.constants.core import DEFAULT_WORKSPACE_DIR, IGNORE_DIRS, DEFAULT_GITIGNORE_RULES, DEFAULT_BASE_BRANCH

class WorkspaceManager:
    def __init__(self, repo_url: str, github_token: str, base_dir: str = DEFAULT_WORKSPACE_DIR, session_id: str = "default"):
        self.repo_url = repo_url
        self.github_token = github_token
        self.base_dir = os.path.abspath(base_dir)
        self.repo_name = urlparse(self.repo_url).path.strip("/").split("/")[-1].replace(".git", "")
        self.repo_path = os.path.join(self.base_dir, f"{self.repo_name}_{session_id}")

    def _get_auth_url(self) -> str:
        url = self.repo_url if self.repo_url.endswith(".git") else self.repo_url + ".git"
        parsed = urlparse(url)
        return f"{parsed.scheme}://x-access-token:{self.github_token}@{parsed.netloc}{parsed.path}"

    def verify_access(self):
        try:
            subprocess.run(["git", "ls-remote", self._get_auth_url()], check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError: 
            return False

    def setup_workspace(self):
        os.makedirs(self.base_dir, exist_ok=True)
        if os.path.exists(self.repo_path): shutil.rmtree(self.repo_path, ignore_errors=True)
        subprocess.run(["git", "clone", self._get_auth_url(), self.repo_path], check=True, capture_output=True, text=True)
        self.run_git_command("config", "user.name", "VibeCoder AI")
        self.run_git_command("config", "user.email", "bot@vibecoder.ai")
        return self.repo_path

    def run_git_command(self, *args, check=True):
        cmd = ["git"] + list(args)
        print(f"💻 Git: {' '.join(cmd).replace(self.github_token, '***')}")
        return subprocess.run(cmd, cwd=self.repo_path if os.path.exists(self.repo_path) else None, check=check, capture_output=True, text=True)

    def get_repo_tree(self, max_lines=200, max_depth=3):
        tree = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
            level = root.replace(self.repo_path, "").count(os.sep)
            if level > max_depth:
                dirs[:] = [] 
                continue
            indent = " " * 4 * level
            tree.append(f"{indent}." if root == self.repo_path else f"{indent}{os.path.basename(root)}/")
            for f in files: 
                if not f.endswith(('.pyc', '.log', '.lock')): tree.append(f"{' ' * 4 * (level + 1)}{f}")
            if len(tree) >= max_lines:
                tree.append(f"{' ' * 4 * level}... (Truncated)")
                break
        return "\n".join(tree[:max_lines + 1])

    def get_available_branches(self):
        self.run_git_command("fetch", "--all", check=False)
        result = self.run_git_command("branch", "-a", check=False)
        branches = set()
        if result.returncode == 0:
            branches = {line.replace('* ', '').replace('remotes/origin/', '').strip() for line in result.stdout.split('\n') if line.strip() and '->' not in line}
        if not branches:
            print("🌱 Empty repository detected. Initializing 'main' branch...")
            self.run_git_command("checkout", "-b", "main", check=False)
            readme_path = os.path.join(self.repo_path, "README.md")
            with open(readme_path, "w", encoding="utf-8") as f: f.write(f"# {self.repo_name}\n\nInitialized by VibeCoder AI.")
            self.run_git_command("add", "README.md", check=False)
            self.run_git_command("commit", "-m", "Initial commit", check=False)
            self.run_git_command("remote", "set-url", "origin", self._get_auth_url(), check=False)
            push_res = self.run_git_command("push", "-u", "origin", "main", check=False)
            if push_res.returncode != 0: raise ValueError("Could not push to GitHub. Check token permissions.")
            return ["main"]
        branch_list = sorted(list(branches))
        if "main" in branch_list: branch_list.insert(0, branch_list.pop(branch_list.index("main")))
        elif "master" in branch_list: branch_list.insert(0, branch_list.pop(branch_list.index("master")))
        return branch_list

    def checkout_base_branch(self, branch_name: str):
        self.run_git_command("checkout", branch_name)
        self.run_git_command("pull", "origin", branch_name)
        return branch_name

    def setup_branch(self, ticket_id: str, base_branch: str = DEFAULT_BASE_BRANCH):
        branch_name = f"feature/{ticket_id.upper()}-{uuid.uuid4().hex[:6]}"
        self.run_git_command("checkout", base_branch)
        self.run_git_command("pull", "origin", base_branch)
        self.run_git_command("checkout", "-b", branch_name)
        return branch_name

    def get_file_diffs(self, modified_files: list):
        diffs = []
        for file_path in modified_files:
            old_result = self.run_git_command("show", f"HEAD:{file_path}", check=False)
            old_content = old_result.stdout if old_result.returncode == 0 else ""
            full_path = os.path.join(self.repo_path, file_path)
            new_content = open(full_path, "r", encoding="utf-8").read() if os.path.exists(full_path) else ""
            diffs.append({"file": file_path, "old_content": old_content, "new_content": new_content})
        return diffs

    def ensure_gitignore(self):
        gitignore_path = os.path.join(self.repo_path, ".gitignore")
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as f: f.write("\n".join(DEFAULT_GITIGNORE_RULES) + "\n")
            return
            
        with open(gitignore_path, "r", encoding="utf-8") as f: existing_rules = f.read().splitlines()
        missing_rules = [rule for rule in DEFAULT_GITIGNORE_RULES if rule not in existing_rules]
        
        if missing_rules:
            with open(gitignore_path, "a", encoding="utf-8") as f: f.write("\n# VibeCoder Auto-Ignores\n" + "\n".join(missing_rules) + "\n")

    def create_pull_request(self, target_branch: str, base_branch: str, title: str, body: str):
        owner_repo = self.repo_url.replace("https://github.com/", "").replace(".git", "")
        url = f"https://api.github.com/repos/{owner_repo}/pulls"
        headers = {"Authorization": f"Bearer {self.github_token}", "Accept": "application/vnd.github.v3+json"}
        data = {"title": title, "head": target_branch, "base": base_branch, "body": body}
        response = requests.post(url, json=data, headers=headers)
        return response.json().get("html_url") if response.status_code == 201 else None

    def create_testing_branch(self, current_branch: str):
        test_branch = f"{current_branch}-testing"
        self.run_git_command("checkout", "-b", test_branch)
        return test_branch

    def wait_for_ci_and_get_logs(self, branch_name: str, timeout_seconds: int = 600) -> dict:
        print(f"☁️ Waiting for GitHub Actions CI to finish on branch '{branch_name}'...")
        repo_path = urlparse(self.repo_url).path.strip("/").replace(".git", "")
        base_api_url = f"https://api.github.com/repos/{repo_path}/actions/runs"
        headers = {"Authorization": f"Bearer {self.github_token}", "Accept": "application/vnd.github.v3+json"}

        start_time = time.time()
        time.sleep(10)

        while (time.time() - start_time) < timeout_seconds:
            try:
                response = requests.get(f"{base_api_url}?branch={branch_name}", headers=headers)
                
                if response.status_code in [401, 403, 429]:
                    return {"success": False, "logs": f"GitHub API Error ({response.status_code}): Rate limited or unauthorized."}
                elif response.status_code != 200:
                    time.sleep(15)
                    continue

                runs = response.json().get("workflow_runs", [])
                if not runs:
                    time.sleep(15)
                    continue

                latest_run = runs[0]
                status, conclusion = latest_run.get("status"), latest_run.get("conclusion")

                if status == "completed":
                    if conclusion == "success":
                        print("✅ GitHub Actions CI Passed!")
                        return {"success": True, "logs": ""}
                    else:
                        print("❌ GitHub Actions CI Failed! Fetching logs...")
                        jobs_response = requests.get(latest_run.get("jobs_url"), headers=headers).json()
                        failed_logs = f"Remote CI Pipeline Failed (Conclusion: {conclusion}).\n"
                        
                        for job in jobs_response.get("jobs", []):
                            if job.get("conclusion") == "failure":
                                failed_logs += f"\nFailed Job: {job.get('name')}\n"
                                for step in job.get("steps", []):
                                    if step.get("conclusion") == "failure": 
                                        failed_logs += f"Failed Step: {step.get('name')}\n"
                        return {"success": False, "logs": failed_logs}
                
                time.sleep(15)
                
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Network error while checking CI: {e}. Retrying...")
                time.sleep(15)
            except Exception as e:
                return {"success": False, "logs": f"Internal Agent Error while checking CI: {str(e)}"}
                
        return {"success": False, "logs": f"CI Pipeline timed out after {timeout_seconds} seconds."}