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
    
    Respond EXACTLY in this format. DO NOT use markdown code blocks (```) inside the file content.
    ---FILE: .github/workflows/vibe-ci.yml---
    name: VibeCoder CI Feedback
    # ... your dynamically generated yaml here ...
    ---END---
    """
    
    raw_response = call_llm(devops_prompt)
    saved_files = []
    extract_and_save_files(raw_response, repo_path, saved_files)
    
    if saved_files:
        print(f"✅ DevOps Agent successfully generated CI workflow: {saved_files[0]}")
    else:
        print("⚠️ DevOps Agent did not generate a workflow file.")
        
    return saved_files