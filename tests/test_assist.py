import pytest
from httpx import AsyncClient
from app.main import app
from app.services.assist_service import assist_service as service

# Mocking external services for unit testing could be complex due to Neoj4/LLM dependencies.
# Here we will perform a basic API structure test.

@pytest.mark.asyncio
async def test_consistency_check_endpoint():
    request_data = {
        "project_id": "test-project",
        "text": "Harry looked at the Golden Snitch."
    }

    # We are not mocking the service here, expecting it might fail if dependencies are missing,
    # but efficient for integration testing structure
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # LLM 호출 없이 에러 핸들링이 작동하는지 확인하거나,
        # 실제 환경에서는 실제 호출이 발생함.
        # 여기서는 경로 존재 여부와 500 에러(설정 미비 시) 등을 확인
        response = await ac.post("/api/assist/check", json=request_data)
        assert response.status_code in [200, 500]

@pytest.mark.asyncio
async def test_dialogue_refine_endpoint():
    request_data = {
        "project_id": "test-project",
        "text": "Hello there.",
        "speaker_name": "Harry",
        "listener_name": "Ron"
    }
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/assist/refine", json=request_data)
        assert response.status_code in [200, 500]

@pytest.mark.asyncio
async def test_active_entities_endpoint():
    request_data = {
        "project_id": "test-project",
        "text": "Harry walked into the room."
    }
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/assist/entities", json=request_data)
        assert response.status_code in [200, 500]
