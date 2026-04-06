from app.agents.base import call_llm, extract_and_save_files
from app.core.config import REVIEWER_WEBHOOK_URL, QA_WEBHOOK_URL

def run_devops_agent(repo_tree: str, repo_path: str):
    """The DevOps Agent. Analyzes the repo and generates a CI workflow with automated webhooks."""
    print("⚙️ DevOps Agent is configuring the Remote CI/CD Environment...")
    
    devops_prompt = f"""
    You are a Lead DevOps Engineer. We need a GitHub Actions CI pipeline to test our code and notify our Reviewer and QA bots.
    
    CURRENT REPOSITORY STRUCTURE:
    {repo_tree}
    
    EXTERNAL WEBHOOKS TO TRIGGER ON PR:
    - Reviewer Bot URL: {REVIEWER_WEBHOOK_URL}
    - QA Bot URL: {QA_WEBHOOK_URL}
    
    INSTRUCTIONS:
    1. Analyze the repository structure to determine the primary language and framework.
    2. Create a GitHub Actions workflow file located EXACTLY at `.github/workflows/vibe-ci.yml`.
    3. TRIGGER: The workflow MUST trigger on `pull_request` events.
    4. TESTING: Include steps to checkout code, setup runtime, install dependencies, and run tests.
    5. NOTIFICATION (CRITICAL): Add a final step using `curl` that triggers AFTER the tests complete. 
       It must send a POST request to BOTH the Reviewer Bot URL and the QA Bot URL.
       The JSON payload must include:
       - "repo": "${{{{ github.repository }}}}"
       - "pr_number": "${{{{ github.event.pull_request.number }}}}"
       - "branch": "${{{{ github.head_ref }}}}"
       - "status": "${{{{ job.status }}}}"
    
    Respond EXACTLY in this format. DO NOT use markdown code blocks (```) inside the file content.
    ---FILE: .github/workflows/vibe-ci.yml---
    name: VibeCoder CI Pipeline
    # ... your dynamically generated yaml here ...
    ---END---
    """
    
    raw_response = call_llm(devops_prompt)
    saved_files = []
    extract_and_save_files(raw_response, repo_path, saved_files)
    
    if saved_files:
        print(f"✅ DevOps Agent successfully generated CI workflow with automated handoffs: {saved_files[0]}")
    else:
        print("⚠️ DevOps Agent did not generate a workflow file.")
        
    return saved_files