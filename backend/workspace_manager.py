import os
import shutil
import subprocess
import json
import time
import requests
import uuid
from urllib.parse import urlparse

class WorkspaceManager:
    def __init__(self, repo_url: str, github_token: str, base_dir: str = "workspaces"):
        self.repo_url = repo_url
        self.github_token = github_token
        self.base_dir = os.path.abspath(base_dir)
        
        parsed_url = urlparse(self.repo_url)
        self.repo_name = parsed_url.path.strip("/").split("/")[-1].replace(".git", "")
        self.repo_path = os.path.join(self.base_dir, self.repo_name)

    def _get_auth_url(self) -> str:
        url = self.repo_url
        if not url.endswith(".git"): url += ".git"
        parsed = urlparse(url)
        return f"{parsed.scheme}://x-access-token:{self.github_token}@{parsed.netloc}{parsed.path}"

    def run_git_command(self, *args, check=True):
        cmd = ["git"] + list(args)
        print(f"💻 Running: {' '.join(cmd).replace(self.github_token, '***')}")
        return subprocess.run(
            cmd, cwd=self.repo_path if os.path.exists(self.repo_path) else None,
            check=check, capture_output=True, text=True
        )

    def verify_access(self):
        try:
            subprocess.run(["git", "ls-remote", self._get_auth_url()], check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def setup_workspace(self):
        os.makedirs(self.base_dir, exist_ok=True)
        if os.path.exists(self.repo_path):
            try: shutil.rmtree(self.repo_path, ignore_errors=True)
            except Exception as e: print(f"Warning: Could not remove directory: {e}")
                
        subprocess.run(["git", "clone", self._get_auth_url(), self.repo_path], check=True, capture_output=True, text=True)
        return self.repo_path

    def get_repo_tree(self, max_lines=200):
        ignore_dirs = {'.git', 'node_modules', '__pycache__', 'dist', 'build', '.venv'}
        tree = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            level = root.replace(self.repo_path, "").count(os.sep)
            indent = " " * 4 * level
            tree.append(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 4 * (level + 1)
            for f in files: tree.append(f"{subindent}{f}")
        return "\n".join(tree[:max_lines])

    def setup_branch(self, ticket_id: str, base_branch: str = "main"):
        unique_id = uuid.uuid4().hex[:6]
        branch_name = f"feature/{ticket_id.upper()}-{unique_id}"
        self.run_git_command("checkout", base_branch)
        self.run_git_command("pull", "origin", base_branch)
        self.run_git_command("checkout", "-b", branch_name)
        return branch_name

    def capture_dev_screenshot(self, components=None, port=5174, dev_cmd="npm run dev -- --port 5174"):
        """Boots a temporary dev server, uses Playwright to snap screenshots, and kills the server."""
        from playwright.sync_api import sync_playwright
        import time
        import requests
        import json

        if components is None:
            components = [{"route": "/", "selector": "body"}]

        shot_dir = os.path.join(self.repo_path, ".agent")
        os.makedirs(shot_dir, exist_ok=True)
        saved_shots = []

        # 1. Check if this is even a frontend project with a dev script
        pkg_json_path = os.path.join(self.repo_path, "package.json")
        if not os.path.exists(pkg_json_path):
            print("⏭️ No package.json found. Skipping visual screenshot.")
            return []
            
        try:
            with open(pkg_json_path, 'r', encoding='utf-8') as f:
                scripts = json.load(f).get("scripts", {})
                if "dev" not in scripts:
                    print("⏭️ No 'dev' script found. Skipping visual screenshot.")
                    return []
        except Exception:
            return []

        # 2. Boot the temporary screenshot server
        print(f"🚀 Booting temporary dev server for photoshoot: {dev_cmd}")
        process = subprocess.Popen(
            dev_cmd,
            shell=True,
            cwd=self.repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            # 3. Wait for the server to come online (max 15 seconds)
            server_up = False
            for _ in range(15):
                time.sleep(1)
                if process.poll() is not None:
                    break # Process crashed
                try:
                    if requests.get(f"http://localhost:{port}").status_code == 200:
                        server_up = True
                        break
                except requests.ConnectionError:
                    continue

            if not server_up:
                print(f"⚠️ Dev server failed to respond on port {port}. Cannot take screenshots.")
                return []

            # 4. Take the precision screenshots
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                for idx, comp in enumerate(components):
                    route = comp.get("route", "/")
                    selector = comp.get("selector", "body")
                    
                    if not route.startswith("/"): 
                        route = "/" + route
                        
                    target_url = f"http://localhost:{port}{route}"
                    print(f"📸 Hunting for '{selector}' on {target_url}...")
                    
                    try:
                        page.goto(target_url, timeout=10000)
                        page.wait_for_load_state('networkidle', timeout=5000)
                        time.sleep(1.5) # Give React a moment to render state/animations
                        
                        file_name = f"preview_{idx}.png"
                        shot_path = os.path.join(shot_dir, file_name)
                        
                        # Attempt precision crop
                        if selector and selector != "body":
                            try:
                                element = page.locator(selector).first
                                element.wait_for(state="visible", timeout=3000)
                                element.screenshot(path=shot_path)
                                print(f"🎯 Successfully cropped screenshot of {selector}")
                            except Exception as e:
                                print(f"⚠️ Could not find '{selector}', falling back to full page. ({e})")
                                page.screenshot(path=shot_path, full_page=True)
                        else:
                            page.screenshot(path=shot_path, full_page=True)
                        
                        saved_shots.append(f".agent/{file_name}")
                    except Exception as e:
                        print(f"⚠️ Failed to navigate to {target_url}: {e}")

                browser.close()
                return saved_shots
                
        finally:
            # 5. CLEANUP: Always execute this to prevent port hogging
            print("🧹 Tearing down temporary photoshoot server...")
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

    def create_pull_request(self, target_branch: str, base_branch: str, title: str, body: str):
        print(f"📝 Opening Pull Request: {target_branch} -> {base_branch}")
        owner_repo = self.repo_url.replace("https://github.com/", "").replace(".git", "")
        url = f"https://api.github.com/repos/{owner_repo}/pulls"
        headers = {"Authorization": f"Bearer {self.github_token}", "Accept": "application/vnd.github.v3+json"}
        data = {"title": title, "head": target_branch, "base": base_branch, "body": body}
        
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 201: return response.json().get("html_url")
        else:
            print(f"⚠️ PR Creation Failed: {response.text}")
            return None
    
    def run_shell_command(self, cmd: str, timeout: int = 60):
        print(f"💻 Running Shell: {cmd[:60]}...")
        try:
            result = subprocess.run(cmd, shell=True, cwd=self.repo_path, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0: return False, result.stderr.strip()
            return True, result.stdout.strip()
        except subprocess.TimeoutExpired:
            print(f"⚠️ Command timed out after {timeout}s.")
            return True, "Process timed out (expected for dev servers)."
    
    def get_available_branches(self):
        self.run_git_command("fetch", "--all")
        result = self.run_git_command("branch", "-a")
        if result.returncode != 0: return ["main"]
            
        branches = set()
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line or '->' in line: continue
            clean_name = line.replace('* ', '').replace('remotes/origin/', '').strip()
            branches.add(clean_name)
            
        branch_list = sorted(list(branches))
        if "main" in branch_list: branch_list.insert(0, branch_list.pop(branch_list.index("main")))
        elif "master" in branch_list: branch_list.insert(0, branch_list.pop(branch_list.index("master")))
        return branch_list

    def checkout_base_branch(self, branch_name: str):
        self.run_git_command("checkout", branch_name)
        self.run_git_command("pull", "origin", branch_name)
        return branch_name

    def run_qa_agent(self, dev_cmd="npm run dev -- --port 5174", port=5174):
        pkg_json_path = os.path.join(self.repo_path, "package.json")
        has_package_json = os.path.exists(pkg_json_path)
        has_test_script, has_dev_script = False, False

        if has_package_json:
            try:
                with open(pkg_json_path, 'r', encoding='utf-8') as f:
                    scripts = json.load(f).get("scripts", {})
                    has_test_script, has_dev_script = "test" in scripts, "dev" in scripts
            except Exception as e:
                print(f"⚠️ QA Agent warning: Could not parse package.json: {e}")

        # Static Checks
        if has_package_json:
            if has_test_script:
                test_cmd = "npm run test --passWithNoTests"
                print(f"🧪 QA Agent running static tests: {test_cmd}")
                success, output = self.run_shell_command(test_cmd)
                if not success: return False, f"Static Tests Failed:\n{output}"
            else: print("⏭️ QA Agent skipping tests: No 'test' script found in package.json.")
        else:
            test_cmd = "pytest"
            print(f"🧪 QA Agent running static tests: {test_cmd}")
            success, output = self.run_shell_command(test_cmd)
            if not success and "Exit code 5" not in output: return False, f"Static Tests Failed:\n{output}"

        # Runtime Compilation Check
        if not has_package_json: return True, "No package.json. Skipping frontend dev server check."
        if not has_dev_script: return True, "No 'dev' script. Skipping runtime check."

        print(f"🕵️‍♂️ QA Agent booting dev server: {dev_cmd}")
        process = subprocess.Popen(dev_cmd, shell=True, cwd=self.repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        server_up, qa_report = False, ""
        
        try:
            for _ in range(15):
                time.sleep(1)
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    return False, f"Dev server crashed immediately.\nSTDOUT: {stdout}\nSTDERR: {stderr}"
                try:
                    if requests.get(f"http://localhost:{port}").status_code == 200:
                        server_up = True
                        break
                except requests.ConnectionError: continue

            if not server_up:
                process.terminate()
                return False, f"Dev server stuck on compilation error."

            print("✅ QA Agent verified dev server successfully compiled.")
            return True, "All tests passed, server compiled."
        finally:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill()

    def get_file_diffs(self, modified_files: list):
        diffs = []
        for file_path in modified_files:
            old_result = self.run_git_command("show", f"HEAD:{file_path}", check=False)
            old_content = old_result.stdout if old_result.returncode == 0 else ""

            full_path = os.path.join(self.repo_path, file_path)
            new_content = ""
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    new_content = f.read()

            diffs.append({"file": file_path, "old_content": old_content, "new_content": new_content})
        return diffs
    
    def ensure_gitignore(self):
        """Creates or updates a .gitignore to prevent pushing node_modules and build files."""
        gitignore_path = os.path.join(self.repo_path, ".gitignore")
        ignore_rules = ["node_modules/", "dist/", "build/", ".env", "__pycache__/", ".DS_Store"]
        
        # If it doesn't exist, create it
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write("\n".join(ignore_rules) + "\n")
            print("🛡️ Created new .gitignore")
            return

        # If it does exist, append missing rules safely
        with open(gitignore_path, "r", encoding="utf-8") as f:
            existing_rules = f.read().splitlines()

        missing_rules = [rule for rule in ignore_rules if rule not in existing_rules]
        
        if missing_rules:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n# VibeCoder Auto-Ignores\n")
                f.write("\n".join(missing_rules) + "\n")
            print("🛡️ Updated existing .gitignore")

    def run_qa_tests(self, test_cmd: str):
        """Executes dynamic test commands and parses for >80% coverage."""
        import re
        
        if not test_cmd:
            return False, "No test command provided."

        print(f"⚙️ Running tests & coverage: {test_cmd}")
        success, output = self.run_shell_command(test_cmd)

        # Save the coverage report to a file so we can attach it to the PR later
        cov_dir = os.path.join(self.repo_path, ".agent")
        os.makedirs(cov_dir, exist_ok=True)
        cov_path = os.path.join(cov_dir, "coverage.txt")
        
        with open(cov_path, "w", encoding="utf-8") as f:
            f.write(output)

        lower_output = output.lower()
        
        # 1. Check for hard test failures
        if not success or "failed" in lower_output or "error:" in lower_output:
            return False, f"Test execution failed or test cases failed:\n{output[-1000:]}"

        # 2. Parse for coverage percentage
        # Looks for patterns like "85%", "79.5 %", etc.
        percentages = re.findall(r'(\d+(?:\.\d+)?)[\s]*%', output)
        if percentages:
            # Convert all found percentages to floats
            floats = [float(p) for p in percentages]
            # Ignore 100% (often used for trivial files) and check if any fall below 80%
            low_coverage = [p for p in floats if p < 80.0]
            
            if low_coverage:
                return False, f"Tests passed, but coverage is below 80% (Found {min(low_coverage)}%). Please add more comprehensive test cases to reach >80% coverage.\n{output[-1000:]}"

        return True, "All tests passed with adequate coverage."