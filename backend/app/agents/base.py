import os
import json
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
    Parses a strict JSON array of file objects.
    Expected format: [{"filepath": "src/main.py", "content": "..."}]
    """
    try:
        files_data = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValueError(f"LLM generation failed: Output was not valid JSON.\nRaw Output: {raw_text[:100]}...")

    if not isinstance(files_data, list):
        raise ValueError("LLM generation failed: Expected a JSON array of file objects.")

    for file_obj in files_data:
        raw_path = file_obj.get("filepath", "").strip()
        content = file_obj.get("content", "")
        
        if not raw_path: 
            continue
        
        full_path = os.path.abspath(os.path.join(repo_path, raw_path))
        repo_abs_path = os.path.abspath(repo_path)
        if not full_path.startswith(repo_abs_path):
            raise ValueError(f"Security Alert: Agent attempted Path Traversal outside workspace directory: {raw_path}")
            
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f: 
            f.write(content.rstrip() + "\n") 
            
        if raw_path not in saved_files: 
            saved_files.append(raw_path)