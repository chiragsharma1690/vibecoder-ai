import os
import shutil
import subprocess
from urllib.parse import urlparse

class WorkspaceManager:
    def __init__(self, repo_url: str, github_token: str, base_dir: str = "workspaces"):
        self.repo_url = repo_url
        self.github_token = github_token
        self.base_dir = os.path.abspath(base_dir)
        
        # Parse the repo name from the URL
        parsed_url = urlparse(self.repo_url)
        self.repo_name = parsed_url.path.strip("/").split("/")[-1].replace(".git", "")
        self.repo_path = os.path.join(self.base_dir, self.repo_name)

    def _get_auth_url(self) -> str:
        """Injects the GitHub token securely into the clone URL."""
        url = self.repo_url
        if not url.endswith(".git"):
            url += ".git"
        parsed = urlparse(url)
        return f"{parsed.scheme}://x-access-token:{self.github_token}@{parsed.netloc}{parsed.path}"

    def run_git_command(self, *args, check=True):
        """Helper to run git commands inside the cloned repository."""
        cmd = ["git"] + list(args)
        print(f"💻 Running: {' '.join(cmd).replace(self.github_token, '***')}")
        
        return subprocess.run(
            cmd,
            cwd=self.repo_path if os.path.exists(self.repo_path) else None,
            check=check,
            capture_output=True,
            text=True
        )

    def verify_access(self):
        """Checks if the token has access to the repository without downloading it."""
        try:
            subprocess.run(
                ["git", "ls-remote", self._get_auth_url()],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def setup_workspace(self):
        """Cleans existing directory and performs a fresh clone."""
        os.makedirs(self.base_dir, exist_ok=True)
        
        if os.path.exists(self.repo_path):
            try:
                shutil.rmtree(self.repo_path, ignore_errors=True)
            except Exception as e:
                print(f"Warning: Could not remove existing directory {self.repo_path}: {e}")
                
        # Clone the repo
        subprocess.run(
            ["git", "clone", self._get_auth_url(), self.repo_path],
            check=True,
            capture_output=True,
            text=True
        )
        return self.repo_path

    def get_repo_tree(self, max_lines=200):
        """Scans the repository to give the LLM structural context."""
        ignore_dirs = {'.git', 'node_modules', '__pycache__', 'dist', 'build', '.venv'}
        tree = []
        
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            # Calculate indentation based on depth
            level = root.replace(self.repo_path, "").count(os.sep)
            indent = " " * 4 * level
            tree.append(f"{indent}{os.path.basename(root)}/")
            
            subindent = " " * 4 * (level + 1)
            for f in files:
                tree.append(f"{subindent}{f}")
                
        return "\n".join(tree[:max_lines])

    def setup_branch(self, ticket_id: str, base_branch: str = "main"):
        """Checks out the base branch, pulls, and creates a feature branch."""
        branch_name = f"feat-{ticket_id.lower()}"
        
        # Checkout the branch the user selected during setup
        self.run_git_command("checkout", base_branch)
        self.run_git_command("pull", "origin", base_branch)
        
        # Create the new feature branch
        result = self.run_git_command("checkout", "-b", branch_name, check=False)
        if result.returncode != 0:
            self.run_git_command("checkout", branch_name)
            
        return branch_name
    
    def run_shell_command(self, cmd: str, timeout: int = 60):
        """Runs a general shell command inside the cloned repository safely."""
        print(f"💻 Running Shell: {cmd[:60]}...")
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                cwd=self.repo_path, # Ensures it runs inside the project folder
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            if result.returncode != 0:
                return False, result.stderr.strip()
            return True, result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            print(f"⚠️ Command timed out after {timeout}s.")
            return True, "Process timed out (expected for dev servers)."
    
    def get_available_branches(self):
        """Fetches a list of all unique remote and local branches."""
        # Ensure we have the latest references from the remote
        self.run_git_command("fetch", "--all")
        result = self.run_git_command("branch", "-a")
        
        if result.returncode != 0:
            return ["main"] # Fallback if something goes wrong
            
        branches = set()
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line or '->' in line: # Skip empty lines and symlinks like HEAD -> origin/main
                continue
                
            # Clean up the output to get just the branch names
            clean_name = line.replace('* ', '').replace('remotes/origin/', '').strip()
            branches.add(clean_name)
            
        # Move 'main' or 'master' to the top of the list if they exist
        branch_list = sorted(list(branches))
        if "main" in branch_list:
            branch_list.insert(0, branch_list.pop(branch_list.index("main")))
        elif "master" in branch_list:
            branch_list.insert(0, branch_list.pop(branch_list.index("master")))
            
        return branch_list

    def checkout_base_branch(self, branch_name: str):
        """Checks out the specified base branch and pulls the latest code."""
        # If the branch doesn't exist locally yet, this will track it from origin
        self.run_git_command("checkout", branch_name)
        self.run_git_command("pull", "origin", branch_name)
        return branch_name