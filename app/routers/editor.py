from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.models.schemas import EditorSaveRequest
from app.dependencies.permissions import check_project_access

router = APIRouter(prefix="/ai-api/editor", tags=["editor"])


@router.post("/save", dependencies=[Depends(check_project_access)])
async def save_editor_content(req: EditorSaveRequest, background_tasks: BackgroundTasks):
    """
    Receives editor content updates and queues them for storage.

    Note: 현재 아키텍처에서 이 엔드포인트는 사용되지 않습니다.
    데이터 저장은 Spring 서버에서 처리하고, 이 서버는 검색만 담당합니다.
    """
    try:
        from app.services.neo4j_service import neo4j_service

        background_tasks.add_task(
            neo4j_service.create_or_update_chunk,
            chunk_uuid=req.chunk_uuid,
            content=req.content,
            project_id=req.project_id,
            embedding=None
        )

        return {
            "status": "accepted",
            "message": "Content queued for storage",
            "task_id": "background_task"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
