import sqlite3
import json
import os
from pathlib import Path

DB_PATH = Path(os.getcwd()) / "vibecoder.db"

def init_db():
    """Initializes the SQLite database and creates the users table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            slack_user_id TEXT PRIMARY KEY,
            credentials TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_slack_user(slack_user_id: str, credentials_dict: dict):
    """Saves or updates a user's credentials."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    creds_json = json.dumps(credentials_dict)
    
    cursor.execute('''
        INSERT INTO users (slack_user_id, credentials)
        VALUES (?, ?)
        ON CONFLICT(slack_user_id) DO UPDATE SET credentials=excluded.credentials
    ''', (slack_user_id, creds_json))
    
    conn.commit()
    conn.close()

def get_slack_user(slack_user_id: str) -> dict | None:
    """Retrieves a user's credentials."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT credentials FROM users WHERE slack_user_id = ?', (slack_user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return json.loads(row[0])
    return None