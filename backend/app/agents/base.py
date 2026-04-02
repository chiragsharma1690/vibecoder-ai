import os
import ollama
import concurrent.futures
from app.core.config import DEFAULT_LLM_MODEL, LLM_TIMEOUT_SECONDS
from app.constants.core import LLM_TEMPERATURE, LLM_CONTEXT_WINDOW

def call_llm(prompt: str, format_type=None, temperature=LLM_TEMPERATURE, model=DEFAULT_LLM_MODEL, timeout=LLM_TIMEOUT_SECONDS):
    """Standardized wrapper for all Ollama LLM requests."""
    options = {"temperature": temperature, "num_ctx": LLM_CONTEXT_WINDOW}
    
    def _generate(): 
        return ollama.generate(model=model, prompt=prompt, format=format_type, options=options)
        
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            response = executor.submit(_generate).result(timeout=timeout) 
            
        raw = response.get("response", "").strip()
        if raw.startswith("```"): 
            raw = "\n".join(raw.split("\n")[1:-1]).strip()
            
        if not raw: raise ValueError("Model returned empty string.")
        return raw
    except concurrent.futures.TimeoutError:
        raise ValueError(f"LLM Generation timed out after {timeout} seconds.")
    except Exception as e:
        raise ValueError(f"LLM Error: {str(e)}")

def extract_and_save_files(raw_text: str, repo_path: str, saved_files: list):
    """
    Parses the custom `---FILE: path---` delimiting format.
    Includes critical protections against Path Traversal vulnerabilities and partial generations.
    """
    if "---FILE:" not in raw_text: 
        return
        
    parts = raw_text.split("---FILE:")
    for part in parts[1:]:
        if not part.strip(): continue
        
        # Guard: Ensure the model actually finished writing the file
        if "---END---" not in part:
            raise ValueError("LLM generation was truncated before completion. Try writing more concise code or increase max tokens.")
            
        raw_path = part.split("---")[0].strip().strip("`'\" \n")
        content = part.split("---")[1].split("---END---")[0].strip()
        
        # Guard: Path Traversal Security check
        # Resolves relative paths (like `../`) and asserts they remain strictly inside the target repo
        full_path = os.path.abspath(os.path.join(repo_path, raw_path))
        repo_abs_path = os.path.abspath(repo_path)
        
        if not full_path.startswith(repo_abs_path):
            raise ValueError(f"Security Alert: Agent attempted Path Traversal outside workspace directory: {raw_path}")
            
        # Strip rogue markdown wrappers that corrupt source code compilation
        if content.startswith("```"):
            first_newline_idx = content.find("\n")
            if first_newline_idx != -1:
                content = content[first_newline_idx+1:]
        if content.endswith("```"):
            content = content[:-3].strip()
        
        # Write to disk safely
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f: 
            f.write(content.strip() + "\n")
            
        if raw_path not in saved_files: 
            saved_files.append(raw_path)