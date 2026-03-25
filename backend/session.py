import os
import json
from fastapi import HTTPException

# Store the session data locally to avoid needing a complex database setup
SESSION_FILE = os.path.join(os.getcwd(), "workspaces", "session.json")

def save_session(data: dict):
    """Saves active credentials (GitHub/Jira tokens) and workspace info to a local JSON file."""
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)

def load_session() -> dict:
    """Loads active credentials. Throws a 400 error if the user hasn't connected yet."""
    if not os.path.exists(SESSION_FILE):
        raise HTTPException(status_code=400, detail="No active session. Please connect first.")
    with open(SESSION_FILE, "r") as f:
        return json.load(f)