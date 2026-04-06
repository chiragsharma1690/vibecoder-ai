import json
import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

from sqlalchemy import create_engine, Column, String, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import ENCRYPTION_KEY
from app.constants.core import DEFAULT_DB_NAME

# --- 1. Encryption Setup (Retained from previous step) ---
try:
    _key = ENCRYPTION_KEY.encode() if ENCRYPTION_KEY else Fernet.generate_key()
    cipher_suite = Fernet(_key)
except ValueError:
    raise ValueError("VIBECODER_ENCRYPTION_KEY in .env must be a valid 32-byte base64-encoded Fernet key.")

# --- 2. Database Engine & Connection Pooling ---
DB_PATH = Path(os.getcwd()) / DEFAULT_DB_NAME
DATABASE_URL = f"sqlite:///{DB_PATH}"

# We add a timeout of 15 seconds to allow concurrent threads to wait in line rather than failing instantly
engine = create_engine(
    DATABASE_URL, 
    connect_args={"timeout": 15, "check_same_thread": False}
)

# Enable Write-Ahead Logging (WAL) for high-concurrency SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 3. ORM Models ---
class User(Base):
    __tablename__ = "users"
    
    slack_user_id = Column(String, primary_key=True, index=True)
    credentials = Column(String, nullable=False)

# --- 4. Database Operations ---
def init_db():
    """Initializes the SQLite database and creates tables from ORM models."""
    Base.metadata.create_all(bind=engine)

def save_slack_user(slack_user_id: str, credentials_dict: dict):
    """Encrypts and saves a user's credentials using SQLAlchemy."""
    # 1. Convert to JSON and Encrypt
    creds_json = json.dumps(credentials_dict)
    encrypted_creds = cipher_suite.encrypt(creds_json.encode('utf-8')).decode('utf-8')
    
    # 2. Database transaction via ORM Session
    with SessionLocal() as db:
        user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
        
        if user:
            # Update existing user
            user.credentials = encrypted_creds
        else:
            # Create new user
            new_user = User(slack_user_id=slack_user_id, credentials=encrypted_creds)
            db.add(new_user)
            
        db.commit()

def get_slack_user(slack_user_id: str) -> dict | None:
    """Retrieves and decrypts a user's credentials using SQLAlchemy."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.slack_user_id == slack_user_id).first()
        
        if not user:
            return None
            
        try:
            # Decrypt the string back into bytes, then decode to JSON string
            decrypted_json = cipher_suite.decrypt(user.credentials.encode('utf-8')).decode('utf-8')
            return json.loads(decrypted_json)
        except InvalidToken:
            print(f"⚠️ Security Alert: Failed to decrypt credentials for user {slack_user_id}. Key may have changed.")
            return None