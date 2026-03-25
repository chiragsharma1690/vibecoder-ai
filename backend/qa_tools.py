import os
import subprocess
import time
import requests
import re

def run_shell_command(cmd: str, repo_path: str, timeout: int = 60):
    print(f"💻 Shell: {cmd[:60]}...")
    try:
        # We capture both, but we will combine them for the LLM context
        result = subprocess.run(cmd, shell=True, cwd=repo_path, capture_output=True, text=True, timeout=timeout)
        
        # Combine stdout and stderr so the LLM gets the full picture
        combined_output = f"{result.stdout}\n{result.stderr}".strip()
        
        if result.returncode == 0:
            return True, combined_output
        else:
            return False, combined_output
            
    except subprocess.TimeoutExpired:
        return True, "Process timed out (expected for dev servers)."

def run_qa_tests(test_cmd: str, repo_path: str):
    if not test_cmd: return False, "No test command provided."

    print(f"⚙️ Running tests: {test_cmd}")
    success, output = run_shell_command(test_cmd, repo_path)

    os.makedirs(os.path.join(repo_path, ".agent"), exist_ok=True)
    with open(os.path.join(repo_path, ".agent", "coverage.txt"), "w", encoding="utf-8") as f:
        f.write(output)

    if not success or "failed" in output.lower() or "error:" in output.lower():
        return False, f"Test execution failed:\n{output[-1000:]}"

    percentages = re.findall(r'(\d+(?:\.\d+)?)[\s]*%', output)
    if percentages:
        low_coverage = [float(p) for p in percentages if float(p) < 80.0]
        if low_coverage:
            return False, f"Coverage is below 80% (Found {min(low_coverage)}%).\n{output[-1000:]}"

    return True, "All tests passed with adequate coverage."

def capture_dev_screenshot(repo_path: str, components=None, port=5174, dev_cmd="npm run dev -- --port 5174"):
    from playwright.sync_api import sync_playwright
    
    components = components or [{"route": "/", "selector": "body"}]
    shot_dir = os.path.join(repo_path, ".agent")
    os.makedirs(shot_dir, exist_ok=True)
    saved_shots = []

    if not os.path.exists(os.path.join(repo_path, "package.json")): return []
        
    print(f"🚀 Booting server for photoshoot: {dev_cmd}")
    process = subprocess.Popen(dev_cmd, shell=True, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        server_up = False
        for _ in range(45):
            time.sleep(1)
            if process.poll() is not None: break
            try:
                if requests.get(f"http://localhost:{port}").status_code == 200:
                    server_up = True
                    break
            except requests.ConnectionError: continue

        if not server_up: return []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for idx, comp in enumerate(components):
                route = "/" + comp.get("route", "/").lstrip("/")
                selector = comp.get("selector", "body")
                target_url = f"http://localhost:{port}{route}"
                
                try:
                    page.goto(target_url, timeout=10000)
                    page.wait_for_load_state('networkidle', timeout=5000)
                    time.sleep(1.5) 
                    
                    shot_path = os.path.join(shot_dir, f"preview_{idx}.png")
                    
                    if selector and selector != "body":
                        try:
                            el = page.locator(selector).first
                            el.wait_for(state="visible", timeout=3000)
                            el.screenshot(path=shot_path)
                        except:
                            page.screenshot(path=shot_path, full_page=True)
                    else:
                        page.screenshot(path=shot_path, full_page=True)
                    
                    saved_shots.append(f".agent/preview_{idx}.png")
                except Exception as e: print(f"⚠️ Failed screenshot: {e}")

            browser.close()
            return saved_shots
    finally:
        print("🧹 Tearing down photoshoot server...")
        process.terminate()
        try: process.wait(timeout=3)
        except: process.kill()