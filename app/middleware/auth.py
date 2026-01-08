from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verifies the JWT token.
    For now, this is a placeholder that accepts any token.
    In production, implement actual JWT decoding and validation.
    """
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Example logic:
    # payload = decode_jwt(token)
    # return payload
    return {"sub": "user-001", "name": "Test User"}

async def get_current_user(token: dict = Depends(verify_token)):
    return token
