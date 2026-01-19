from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal


class EditorSaveRequest(BaseModel):
    chunk_uuid: str
    content: str
    project_id: str
    user_id: str
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    session_id: str
    message: str
    project_id: str
    user_id: str
    conversation_history: Optional[List[Dict[str, str]]] = []
    context_data: Optional[Dict[str, Any]] = None


class SourceChunk(BaseModel):
    """검색 결과 소스 청크/문장"""
    id: str  # chunk_uuid 또는 sentence_id
    content: str
    score: float  # 유사도 점수 (0~1)
    source: Literal["neo4j", "postgresql"]  # 데이터 소스
    source_type: Literal["chunk", "sentence"]  # 컨텐츠 타입
    metadata: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[SourceChunk]


class StreamToken(BaseModel):
    type: Literal["token", "sources", "done", "error"]
    content: Optional[str] = None
    sources: Optional[List[SourceChunk]] = None
    error: Optional[str] = None
