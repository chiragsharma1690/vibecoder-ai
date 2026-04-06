import os
import json
import ollama
import concurrent.futures
from app.core.config import DEFAULT_LLM_MODEL, LLM_TIMEOUT_SECONDS
from app.constants.core import LLM_TEMPERATURE, LLM_CONTEXT_WINDOW

def call_llm(prompt: str, format_type=None, temperature=LLM_TEMPERATURE, model=DEFAULT_LLM_MODEL, timeout=LLM_TIMEOUT_SECONDS):
    """Standardized wrapper for all Ollama LLM requests."""
    options = {
        "temperature": temperature, 
        "num_ctx": LLM_CONTEXT_WINDOW,
        "num_predict": -1 
    }    
    def _generate(): 
        return ollama.generate(model=model, prompt=prompt, format=format_type, options=options)
        
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            response = executor.submit(_generate).result(timeout=timeout) 
            
        raw = response.get("response", "").strip()
            
        if not raw: raise ValueError("Model returned empty string.")
        return raw
    except concurrent.futures.TimeoutError:
        raise ValueError(f"LLM Generation timed out after {timeout} seconds.")
    except Exception as e:
        raise ValueError(f"LLM Error: {str(e)}")

def extract_and_save_files(raw_text: str, repo_path: str, saved_files: list):
    """Parses JSON robustly using bracket extraction, ignoring all markdown and conversational text."""
    
    start_idx = raw_text.find('[')
    start_dict = raw_text.find('{')
    
    if start_idx != -1 or start_dict != -1:
        start = min(i for i in [start_idx, start_dict] if i != -1)
        end_idx = raw_text.rfind(']')
        end_dict = raw_text.rfind('}')
        end = max(end_idx, end_dict)
        
        if start != -1 and end != -1 and end >= start:
            raw_text = raw_text[start:end+1]

    try:
        files_data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM generation failed: Output was not valid JSON. {str(e)}\nRaw Output: {raw_text[:100]}...")

    extracted_files = []

    if isinstance(files_data, list):
        extracted_files = files_data
    elif isinstance(files_data, dict):
        if ("filepath" in files_data or "file" in files_data) and ("content" in files_data or "code" in files_data):
            extracted_files = [files_data]
        else:
            for key, value in files_data.items():
                if isinstance(value, list):
                    valid_objects = [item for item in value if isinstance(item, dict) and ("filepath" in item or "file" in item or "path" in item)]
                    extracted_files.extend(valid_objects)

    if not extracted_files:
        raise ValueError(f"LLM generation failed: Could not find valid file objects.\nParsed keys: {list(files_data.keys()) if isinstance(files_data, dict) else type(files_data)}")

    files_written = 0
    for file_obj in extracted_files:
        if not isinstance(file_obj, dict): continue
            
        raw_path = str(file_obj.get("filepath") or file_obj.get("file") or file_obj.get("path") or "").strip()
        content = str(file_obj.get("content") or file_obj.get("code") or file_obj.get("source") or "")
        if not raw_path: continue
        
        full_path = os.path.abspath(os.path.join(repo_path, raw_path))
        repo_abs_path = os.path.abspath(repo_path)
        
        if not full_path.startswith(repo_abs_path):
            raise ValueError(f"Security Alert: Path Traversal blocked: {raw_path}")
            
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f: 
            f.write(content.rstrip() + "\n") 
            
        if raw_path not in saved_files: 
            saved_files.append(raw_path)
        files_written += 1
        
    if files_written == 0:
        raise ValueError("LLM generated JSON, but no valid filepaths and contents were found inside it.")