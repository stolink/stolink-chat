from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.services.chat_service import chat_service
from app.services.redis_service import redis_service
from app.dependencies.permissions import check_project_access
from pydantic import BaseModel

from app.config import settings

# Prefix 변경: CloudFront 호환을 위해 /api/ai-chat 사용
router = APIRouter(prefix="/api/ai-chat", tags=["chat"])

# 조건부 인증: 로컬이 아닐 때만 인증 적용
_auth_dependency = [Depends(check_project_access)] if settings.APP_ENV != "local" else []

@router.post("/stream", dependencies=_auth_dependency)
async def chat_stream_endpoint(req: ChatRequest):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    Uses session_id for context and Redis for history.
    """
    return StreamingResponse(
        chat_service.chat_stream(req.message, req.project_id, req.session_id, req.user_id),
        media_type="text/event-stream"
    )

class StopRequest(BaseModel):
    session_id: str

# TODO: 테스트 완료 후 인증 다시 활성화
@router.post("/stop", dependencies=_auth_dependency)
async def stop_chat_generation(req: StopRequest):
    """
    Publishes a STOP signal to the given session.
    """
    await redis_service.publish_stop_signal(req.session_id)
    return {"status": "signal_sent", "session_id": req.session_id}


# TODO: 테스트 완료 후 인증 다시 활성화
@router.get("/history/{session_id}", dependencies=_auth_dependency)
async def get_chat_history(session_id: str, limit: int = 20):
    """
    Retrieves chat history for a session.
    
    Args:
        session_id: Session identifier (typically userId-projectId)
        limit: Maximum number of messages to return (default: 20)
    
    Returns:
        Session history with messages
    """
    history = await redis_service.get_session_history(session_id, limit=limit)
    return {
        "session_id": session_id,
        "messages": history,
        "count": len(history)
    }
