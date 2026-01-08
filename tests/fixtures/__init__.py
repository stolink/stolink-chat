"""Test fixtures for StoLink Chat Service."""

import json
from pathlib import Path
from typing import Any


def load_test_data() -> dict[str, Any]:
    """Load test data from JSON file."""
    fixture_path = Path(__file__).parent / "test_data.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_editor_chunks() -> list[dict[str, Any]]:
    """Get editor content chunks for testing."""
    data = load_test_data()
    return data["editor_chunks"]


def get_chat_test_cases() -> list[dict[str, Any]]:
    """Get chat test cases."""
    data = load_test_data()
    return data["chat_test_cases"]


def get_conversation_samples() -> list[dict[str, Any]]:
    """Get multi-turn conversation samples."""
    data = load_test_data()
    return data["conversation_history_samples"]


def get_edge_cases() -> list[dict[str, Any]]:
    """Get edge case test data."""
    data = load_test_data()
    return data["edge_cases"]


def get_test_project_id() -> str:
    """Get test project ID."""
    data = load_test_data()
    return data["project_id"]


def get_test_user_id() -> str:
    """Get test user ID."""
    data = load_test_data()
    return data["user_id"]
