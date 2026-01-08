from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import setup_logging
from app.middleware.error_handler import global_exception_handler
from app.services.postgres_service import postgres_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 라이프사이클 관리"""
    # 시작 시
    setup_logging()
    await postgres_service.initialize()

    yield

    # 종료 시
    await postgres_service.close()


app = FastAPI(title="StoLink Chatbot Service", lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(Exception, global_exception_handler)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Import and include routers (will be added later)
from app.routers import editor, chat
app.include_router(editor.router)
app.include_router(chat.router)
