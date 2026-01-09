"""Permission dependencies for chatbot API.

Handles authentication and authorization checks.
"""

from fastapi import Depends, HTTPException
from typing import Optional

from app.middleware.auth import verify_token


async def check_project_access(user: dict = Depends(verify_token)) -> dict:
    """
    Check if user has access to the project.
    
    Requires authenticated user. In the future, can add
    project ownership verification if needed.
    
    Args:
        user: Verified user from JWT token
        
    Returns:
        dict: User info containing 'sub' (userId)
        
    Raises:
        HTTPException 401 if not authenticated
    """
    if not user or not user.get("sub"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return user


async def get_optional_user(user: dict = Depends(verify_token)) -> Optional[dict]:
    """
    Get current user if authenticated, None otherwise.
    
    For endpoints that support both authenticated and anonymous access.
    """
    try:
        return user
    except HTTPException:
        return None
