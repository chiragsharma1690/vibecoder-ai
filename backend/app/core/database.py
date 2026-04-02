import sqlite3
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import ENCRYPTION_KEY
from app.constants.core import DEFAULT_DB_NAME

try:
    _key = ENCRYPTION_KEY.encode() if ENCRYPTION_KEY else Fernet.generate_key()
    cipher_suite = Fernet(_key)
except ValueError:
    raise ValueError("VIBECODER_ENCRYPTION_KEY in .env must be a valid 32-byte base64-encoded Fernet key.")

DB_PATH = Path(os.getcwd()) / DEFAULT_DB_NAME

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
    """Encrypts and saves a user's credentials."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    creds_json = json.dumps(credentials_dict)
    encrypted_creds = cipher_suite.encrypt(creds_json.encode('utf-8')).decode('utf-8')
    
    cursor.execute('''
        INSERT INTO users (slack_user_id, credentials)
        VALUES (?, ?)
        ON CONFLICT(slack_user_id) DO UPDATE SET credentials=excluded.credentials
    ''', (slack_user_id, encrypted_creds))
    
    conn.commit()
    conn.close()

def get_slack_user(slack_user_id: str) -> dict | None:
    """Retrieves and decrypts a user's credentials."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT credentials FROM users WHERE slack_user_id = ?', (slack_user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        encrypted_creds = row[0]
        try:
            # 1. Decrypt the string back into bytes, then decode to JSON string
            decrypted_json = cipher_suite.decrypt(encrypted_creds.encode('utf-8')).decode('utf-8')
            
            # 2. Convert JSON string back to dict
            return json.loads(decrypted_json)
        except InvalidToken:
            print(f"⚠️ Security Alert: Failed to decrypt credentials for user {slack_user_id}. Key may have changed.")
            return None
            
    return None