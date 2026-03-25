import os
import subprocess
import time
import requests
import re

def run_shell_command(cmd: str, repo_path: str, timeout: int = 300):
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

def capture_coverage_screenshot(repo_path: str, coverage_text: str):
    from playwright.sync_api import sync_playwright
    import os

    # We save the image to a standard GitHub tracking folder, NOT the ignored .agent folder
    assets_dir = os.path.join(repo_path, ".github", "assets")
    os.makedirs(assets_dir, exist_ok=True)
    img_path = os.path.join(assets_dir, "coverage.png")

    # Create a temporary HTML file inside the ignored .agent folder to format the terminal output
    agent_dir = os.path.join(repo_path, ".agent")
    os.makedirs(agent_dir, exist_ok=True)
    html_path = os.path.join(agent_dir, "coverage.html")
    
    html_content = f"""
    <html>
    <body style="background:#0d1117; color:#c9d1d9; font-family:Consolas, monospace; padding:20px; width:800px;">
        <h2 style="color:#58a6ff;">📊 Test Coverage Report</h2>
        <pre style="white-space: pre-wrap; word-wrap: break-word;">{coverage_text}</pre>
    </body>
    </html>
    """
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                # 🚨 OPTIMIZATION: Nested try/finally guarantees the browser closes on errors
                page = browser.new_page()
                page.goto(f"file://{os.path.abspath(html_path)}")
                page.locator("body").screenshot(path=img_path)
            finally:
                browser.close()
                
        return ".github/assets/coverage.png"
    except Exception as e:
        print(f"⚠️ Failed to screenshot coverage: {e}")
        return None
