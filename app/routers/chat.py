from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.services.chat_service import chat_service
from app.services.redis_service import redis_service
from app.dependencies.permissions import check_project_access
from pydantic import BaseModel

router = APIRouter(prefix="/ai-api/chat", tags=["chat"])

@router.post("/stream", dependencies=[Depends(check_project_access)])
async def chat_stream_endpoint(req: ChatRequest):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    Uses session_id for context and Redis for history.
    """
    return StreamingResponse(
        chat_service.chat_stream(req.message, req.project_id, req.session_id),
        media_type="text/event-stream"
    )

class StopRequest(BaseModel):
    session_id: str

@router.post("/stop")
async def stop_chat_generation(req: StopRequest):
    """
    Publishes a STOP signal to the given session.
    """
    await redis_service.publish_stop_signal(req.session_id)
    return {"status": "signal_sent", "session_id": req.session_id}
