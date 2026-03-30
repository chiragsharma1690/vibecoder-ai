from app.agents.base import call_llm, extract_and_save_files

def run_developer_agent(prompt: str, repo_path: str, saved_files: list):
    """The Developer Agent. Executes the Architect's plan and outputs raw source code."""
    print("💻 Developer Agent is writing implementation code...")
    raw_text = call_llm(prompt)
    extract_and_save_files(raw_text, repo_path, saved_files)