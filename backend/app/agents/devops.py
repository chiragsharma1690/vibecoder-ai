from app.agents.base import call_llm, extract_and_save_files

def run_devops_agent(repo_tree: str, repo_path: str):
    """The DevOps Agent. Analyzes the repo and generates a CI workflow."""
    print("⚙️ DevOps Agent is configuring the Remote CI/CD Environment...")
    
    devops_prompt = f"""
    You are a Lead DevOps Engineer. We need a GitHub Actions CI pipeline to provide remote feedback for our coding agent.
    
    CURRENT REPOSITORY STRUCTURE:
    {repo_tree}
    
    INSTRUCTIONS:
    1. Analyze the repository structure to determine the primary language and framework.
    2. Create or update a GitHub Actions workflow file located at `.github/workflows/vibe-ci.yml`.
    3. The workflow MUST trigger on `push` to branches matching `feature/*`.
    4. The workflow MUST include steps to checkout code, setup runtime, install dependencies, and run tests.
    
    CRITICAL INSTRUCTION:
    You MUST output your response as a strict JSON array containing the workflow file.
    DO NOT wrap the JSON in markdown blocks. Just return the raw JSON array.
    
    Exact Schema Required:
    [
      {{
        "filepath": ".github/workflows/vibe-ci.yml",
        "content": "yaml content here..."
      }}
    ]
    """
    
    # Request JSON format natively from Ollama
    raw_response = call_llm(devops_prompt, format_type="json")
    saved_files = []
    extract_and_save_files(raw_response, repo_path, saved_files)
    
    if saved_files:
        print(f"✅ DevOps Agent successfully generated CI workflow: {saved_files[0]}")
    else:
        print("⚠️ DevOps Agent did not generate a workflow file.")
        
    return saved_files