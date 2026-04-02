import jwt
from fastapi import Request, HTTPException
from app.core.config import SECRET_KEY

# Import constants
from app.constants.core import JWT_ALGORITHM, SESSION_COOKIE_NAME

def create_session_token(session_data: dict) -> str:
    """Creates a cryptographically signed JWT string."""
    return jwt.encode(session_data, SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_current_session(request: Request) -> dict:
    """Extracts and verifies the cryptographically signed JWT session cookie."""
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Session cookie missing. Please reconnect.")
        
    try:
        session_data = jwt.decode(session_cookie, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return session_data
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please reconnect.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token. Security alert.")