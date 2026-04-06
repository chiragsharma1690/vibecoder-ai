import base64
import json
from fastapi import Request, HTTPException

def get_current_session(request: Request) -> dict:
    """Extracts and decodes the base64 session cookie from the frontend."""
    session_cookie = request.cookies.get("vibecoder_session")
    
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Session cookie missing. Please reconnect.")
        
    try:
        # Decode the base64 cookie back into a Python dictionary
        decoded_bytes = base64.b64decode(session_cookie)
        session_data = json.loads(decoded_bytes.decode('utf-8'))
        return session_data
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session cookie format.")