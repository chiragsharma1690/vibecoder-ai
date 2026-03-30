import subprocess

def run_shell_command(cmd: str, repo_path: str, timeout: int = 300):
    """
    Executes an arbitrary shell command safely within the repository folder.
    Provides a generous timeout to allow for heavy package installations.
    """
    print(f"💻 Shell: {cmd[:60]}...")
    try:
        # The Phantom Keyboard simulates a human typing "y" and hitting "Enter"
        phantom_keystrokes = "y\n" * 10
        
        result = subprocess.run(
            cmd, shell=True, cwd=repo_path, capture_output=True, text=True, 
            timeout=timeout, input=phantom_keystrokes
        )
        combined_output = f"{result.stdout}\n{result.stderr}".strip()
        
        if result.returncode == 0:
            return True, combined_output
        else:
            return False, combined_output
            
    except subprocess.TimeoutExpired:
        return False, f"Process timed out after {timeout} seconds. The command likely froze."