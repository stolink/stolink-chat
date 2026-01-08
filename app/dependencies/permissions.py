from fastapi import Depends, HTTPException, Request
from app.middleware.auth import get_current_user
from typing import Optional


async def get_optional_user(request: Request) -> Optional[dict]:
    """
    Returns the current user if authenticated, None otherwise.
    For development/testing, allows unauthenticated requests.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    # In production, validate the token here
    return {"sub": "user-001", "name": "Test User"}


async def check_project_access(user: Optional[dict] = Depends(get_optional_user)):
    """
    Checks if the user has access to the project.
    For now, allows all requests (development mode).
    In production, implement proper access control.
    """
    # Development mode: allow all requests
    # Production: uncomment below to require authentication
    # if not user:
    #     raise HTTPException(status_code=401, detail="Not authenticated")

    return True
