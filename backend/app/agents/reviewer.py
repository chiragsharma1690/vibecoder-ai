from app.agents.base import call_llm

def run_reviewer_agent(ticket_id: str, jira_context: str, repo_tree: str, diff_text: str):
    """The Senior Tech Lead Agent. Performs deep static analysis locally before pushing."""
    print("🧐 Senior Reviewer Agent is performing deep static analysis...")
    
    reviewer_prompt = f"""
    You are the Senior Staff Software Engineer and Tech Lead. 
    A developer has just submitted code to resolve the following Jira Ticket:
    TICKET ({ticket_id}):\n{jira_context}
    
    CURRENT REPOSITORY STRUCTURE:
    {repo_tree}
    
    SUBMITTED FILES (NEW CODE / DIFFS):
    {diff_text}
    
    INSTRUCTIONS:
    Perform a DEEP, ruthless static analysis of the submitted code. Evaluate the submission against these 5 pillars:
    1. FOLDER STRUCTURE & ARCHITECTURE: Did they hallucinate a nested folder (like `src/src/`)?
    2. DRY PRINCIPLES & REPETITION: Is there duplicated logic?
    3. LINTING & IMPORTS: Scan for missing imports (e.g., React, useState). Are there obvious typos or syntax errors?
    4. SCOPE CREEP: Does the code strictly solve the Jira ticket?
    5. PLACEHOLDERS: Did they leave any "TODO" or "insert code here" comments?
    
    YOUR DECISION:
    If the code passes ALL checks, respond with EXACTLY the word "APPROVED" on the very first line.
    If the code fails ANY critical check, respond with EXACTLY the word "REJECTED" on the very first line, followed by a numbered list of actionable fixes.
    """
    
    review_output = call_llm(reviewer_prompt)
    is_approved = review_output.strip().upper().startswith("APPROVED")
    return is_approved, review_output