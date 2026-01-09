"""JWT token verification middleware.

Verifies JWT tokens from Spring backend using shared JWT_SECRET.
Supports both Authorization header and HttpOnly cookie.
"""

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.config import settings

# HTTPBearer with auto_error=False to allow cookie fallback
security = HTTPBearer(auto_error=False)


def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract access_token from HttpOnly cookie."""
    return request.cookies.get("access_token")


async def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Verify JWT token.
    
    1. Check Authorization header first (Bearer token)
    2. Fall back to HttpOnly cookie if no header
    
    Returns:
        dict with 'sub' (userId as UUID string) and 'type' ('access')
    
    Raises:
        HTTPException 401 if token is missing, expired, or invalid
    """
    # Development mode fallback: if JWT_SECRET is not set, allow all requests
    if not settings.JWT_SECRET:
        return {"sub": "dev-user", "type": "access", "dev_mode": True}
    
    token = None
    
    # 1. Try Authorization header
    if credentials:
        token = credentials.credentials
    
    # 2. Try cookie if no header
    if not token:
        token = get_token_from_cookie(request)
    
    if not token:
        raise HTTPException(status_code=401, detail="Token not provided")
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify token type is 'access'
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        return {
            "sub": payload["sub"],  # userId (UUID string)
            "type": payload["type"]
        }
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


async def get_current_user(token: dict = Depends(verify_token)) -> dict:
    """Get current user from verified token."""
    return token
