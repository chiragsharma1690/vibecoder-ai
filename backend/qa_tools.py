import os
import subprocess
import time
import requests
import re

def run_shell_command(cmd: str, repo_path: str, timeout: int = 300):
    """
    Executes an arbitrary shell command safely within the repository folder.
    Provides a generous 5-minute timeout (300s) to allow for heavy package installations.
    """
    print(f"💻 Shell: {cmd[:60]}...")
    try:
        # The Phantom Keyboard
        # We simulate a human typing "y" and hitting "Enter" 10 times.
        # If the command asks a question, it consumes a "y\n" from this string.
        # If the command never asks a question, it simply ignores the extra input.
        phantom_keystrokes = "y\n" * 10
        
        # Capture both standard output and standard error
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=repo_path, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            input=phantom_keystrokes
        )
        
        # Combine stdout and stderr so the LLM gets the full picture
        combined_output = f"{result.stdout}\n{result.stderr}".strip()
        
        if result.returncode == 0:
            return True, combined_output
        else:
            return False, combined_output
            
    except subprocess.TimeoutExpired:
        return False, f"Process timed out after {timeout} seconds. The command likely froze."
