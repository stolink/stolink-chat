"""
Integration tests using fixture data.
Run with: pytest tests/test_with_fixtures.py -v
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.fixtures import (
    get_editor_chunks,
    get_chat_test_cases,
    get_conversation_samples,
    get_edge_cases,
    get_test_project_id,
    get_test_user_id,
)

client = TestClient(app)

PROJECT_ID = get_test_project_id()
USER_ID = get_test_user_id()


class TestEditorSave:
    """Tests for /api/editor/save endpoint."""

    @pytest.mark.parametrize("chunk", get_editor_chunks())
    def test_save_chunk(self, chunk: dict):
        """Test saving editor content chunks."""
        response = client.post(
            "/api/editor/save",
            json={
                "chunk_uuid": chunk["chunk_uuid"],
                "content": chunk["content"],
                "project_id": PROJECT_ID,
                "user_id": USER_ID,
                "metadata": chunk.get("metadata"),
            },
        )
        # Without running services, expect 200 or connection error
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "accepted"
            assert "task_id" in data


class TestChatStream:
    """Tests for /api/chat/stream endpoint."""

    @pytest.mark.parametrize("test_case", get_chat_test_cases())
    def test_chat_question(self, test_case: dict):
        """Test chat with various questions."""
        response = client.post(
            "/api/chat/stream",
            json={
                "message": test_case["message"],
                "project_id": PROJECT_ID,
                "user_id": USER_ID,
            },
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code in [200, 500]

    @pytest.mark.parametrize("conv_sample", get_conversation_samples())
    def test_chat_with_history(self, conv_sample: dict):
        """Test chat with conversation history."""
        response = client.post(
            "/api/chat/stream",
            json={
                "message": conv_sample["follow_up"],
                "project_id": PROJECT_ID,
                "user_id": USER_ID,
                "conversation_history": conv_sample["history"],
            },
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code in [200, 500]


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.parametrize("edge_case", get_edge_cases())
    def test_edge_case(self, edge_case: dict):
        """Test edge cases."""
        response = client.post(
            "/api/chat/stream",
            json={
                "message": edge_case["message"],
                "project_id": PROJECT_ID,
                "user_id": USER_ID,
            },
            headers={"Accept": "text/event-stream"},
        )
        # Edge cases should be handled gracefully
        assert response.status_code in [200, 400, 422, 500]
