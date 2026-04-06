from app.agents.base import call_llm, extract_and_save_files

def run_developer_agent(prompt: str, repo_path: str, saved_files: list):
    """The Developer Agent. Executes the Architect's plan and outputs raw source code as JSON."""
    print("💻 Developer Agent is writing implementation code...")
    
    developer_prompt = f"""
    {prompt}
    
    CRITICAL INSTRUCTION:
    You MUST output your response as a strict JSON array containing the files you modified or created.
    DO NOT wrap the JSON in markdown code blocks. Just return the raw JSON array.
    
    Exact Schema Required:
    [
      {{
        "filepath": "relative/path/to/file.ext",
        "content": "raw source code here..."
      }}
    ]
    """
    
    raw_text = call_llm(developer_prompt, format_type="json")
    extract_and_save_files(raw_text, repo_path, saved_files)
