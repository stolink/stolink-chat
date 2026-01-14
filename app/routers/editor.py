from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.models.schemas import EditorSaveRequest

from app.dependencies.permissions import check_project_access

router = APIRouter(prefix="/api/ai-api/editor", tags=["editor"])

@router.post("/save", dependencies=[Depends(check_project_access)])
async def save_editor_content(req: EditorSaveRequest, background_tasks: BackgroundTasks):
    """
    Receives editor content updates and queues them for embedding using FastAPI BackgroundTasks.
    """
    try:
        # Save to Neo4j directly (without embedding)
        # Background task is used to avoid blocking API
        from app.services.neo4j_service import neo4j_service

        background_tasks.add_task(
            neo4j_service.create_or_update_chunk,
            chunk_uuid=req.chunk_uuid,
            content=req.content,
            project_id=req.project_id,
            embedding=None # Explicitly None
        )

        return {
            "status": "accepted",
            "message": "Content queued for storage (embedding skipped)",
            "task_id": "background_task"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
