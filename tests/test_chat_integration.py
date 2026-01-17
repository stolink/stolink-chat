import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.chat_service import ChatService, ChatMode, ChatContext
from app.services.persona_service import PersonaContext
import json

# Mock Data
MOCK_PROJECT_ID = "test-project-id"
MOCK_SESSION_ID = "test-session-id"
MOCK_CHARACTER_NAME = "Elara"
MOCK_RELATIONSHIP_DATA = {
    "id": 1,
    "sourceId": "char1",
    "sourceName": "Elara",
    "targetId": "char2",
    "targetName": "Kael",
    "types": ["FRIEND"],
    "strength": 8,
    "description": "Close friends",
    "bidirectional": True,
    "since": None,
    "revealedInChapter": None
}

@pytest.fixture
def chat_service():
    with patch("app.services.chat_service.ChatBedrock") as MockBedrock:
        service = ChatService()
        # Mock LLM response stream
        async def mock_astream(*args, **kwargs):
            yield MagicMock(content="Hello, I am Elara.")
        service.llm.astream = mock_astream
        service.llm.ainvoke = AsyncMock(return_value=MagicMock(content="Y")) # Intent check passes
        return service

@pytest.fixture
def mock_services():
    with patch("app.services.chat_service.neo4j_service") as mock_neo4j, \
         patch("app.services.chat_service.persona_service") as mock_persona, \
         patch("app.services.chat_service.unified_search_service") as mock_search, \
         patch("app.services.chat_service.redis_service") as mock_redis, \
         patch("app.services.chat_service.postgres_service") as mock_postgres, \
         patch("app.services.chat_service.consistency_service") as mock_consistency, \
         patch("app.services.chat_service.embedding_service") as mock_embedding:

        # Setup common mocks
        # Redis
        mock_redis.add_message_to_history = AsyncMock()
        mock_redis.get_session_history = AsyncMock(return_value=[])

        # Mock PubSub listener
        mock_listener = MagicMock()
        mock_listener.get_message = AsyncMock(return_value=None)
        mock_listener.close = AsyncMock()
        mock_redis.create_stop_listener = AsyncMock(return_value=mock_listener)

        # Postgres
        mock_postgres.save_chat_log = AsyncMock()

        # Search & Embedding
        mock_embedding.get_embedding.return_value = [0.1, 0.2, 0.3]
        mock_search.search = AsyncMock(return_value={"sections": [], "characters": [], "events": []})

        # Consistency
        mock_consistency.get_relevant_conflicts = AsyncMock(return_value=[])
        mock_consistency.format_conflicts_for_response.return_value = None

        # Persona
        mock_persona.detect_persona_request.return_value = None
        mock_persona.build_persona_context = AsyncMock(return_value=None)
        mock_persona.strip_persona_mention.return_value = "processed message"
        mock_persona.generate_persona_card.return_value = {}
        mock_persona.generate_persona_prompt.return_value = "system prompt"

        # Neo4j (sync methods in service? check service definition)
        # Looking at original code: neo4j_service methods are called via loop.run_in_executor OR directly?
        # In chat_service:
        #   run_in_executor(embedding_service.get_embedding) -> sync
        #   unified_search_service.search -> async
        #   consistency_service.get_relevant_conflicts -> async
        #   persona_service.build_persona_context -> async
        #   neo4j_service.get_relationship_between -> sync (called directly in _check_relationship_query)

        mock_neo4j.get_relationship_between.return_value = None

        yield {
            "neo4j": mock_neo4j,
            "persona": mock_persona,
            "search": mock_search,
            "redis": mock_redis,
            "postgres": mock_postgres
        }

@pytest.mark.asyncio
async def test_persona_mode_activation(chat_service, mock_services):
    """Verify that addressing a character triggers persona mode."""
    # Setup
    mock_services["persona"].detect_persona_request.return_value = "Elara"
    mock_services["persona"].build_persona_context.return_value = PersonaContext(
        character={"name": "Elara", "id": "char1"},
        relationships=[],
        recent_events=[]
    )
    mock_services["persona"].generate_persona_card.return_value = {"type": "cards", "cards": []}
    mock_services["persona"].strip_persona_mention.return_value = "Hello"
    mock_services["persona"].generate_persona_prompt.return_value = "System Prompt"

    # Execute
    responses = []
    async for chunk in chat_service.chat_stream("Elara, hello", MOCK_PROJECT_ID, MOCK_SESSION_ID):
        if "data: " in chunk:
            data = json.loads(chunk.replace("data: ", ""))
            responses.append(data)

    # Verify
    mock_services["persona"].detect_persona_request.assert_called_once()
    mock_services["persona"].build_persona_context.assert_called_once_with(MOCK_PROJECT_ID, "Elara")

    # Check if persona card was sent
    assert any(r.get("type") == "cards" for r in responses)

@pytest.mark.asyncio
async def test_relationship_query_trigger(chat_service, mock_services):
    """Verify that asking about relationships triggers a relationship card."""
    # Setup
    mock_services["persona"].detect_persona_request.return_value = None # Normal mode
    mock_services["search"].search.return_value = {
        "characters": [
            {"name": "Elara", "id": "char1"},
            {"name": "Kael", "id": "char2"}
        ]
    }
    mock_services["neo4j"].get_relationship_between.return_value = MOCK_RELATIONSHIP_DATA

    message = "Elara와 Kael의 관계는 어때?"

    # Execute
    responses = []
    async for chunk in chat_service.chat_stream(message, MOCK_PROJECT_ID, MOCK_SESSION_ID):
        if "data: " in chunk:
            data = json.loads(chunk.replace("data: ", ""))
            responses.append(data)

    # Verify
    mock_services["neo4j"].get_relationship_between.assert_called_with(MOCK_PROJECT_ID, "char1", "char2")

    # Check if relationship card was sent
    card_response = next((r for r in responses if r.get("type") == "cards"), None)
    assert card_response is not None
    assert card_response["cards"][0]["cardType"] == "relationship"
    assert card_response["cards"][0]["data"]["sourceCharacter"]["name"] == "Elara"

@pytest.mark.asyncio
async def test_normal_rag_flow(chat_service, mock_services):
    """Verify normal RAG flow with source retrieval."""
    # Setup
    mock_services["persona"].detect_persona_request.return_value = None
    mock_services["search"].search.return_value = {
        "sections": [{"section_id": "s1", "content": "Story content", "score": 0.9}],
        "characters": [],
        "events": []
    }

    # Execute
    responses = []
    async for chunk in chat_service.chat_stream("Tell me a story", MOCK_PROJECT_ID, MOCK_SESSION_ID):
        if "data: " in chunk:
            data = json.loads(chunk.replace("data: ", ""))
            responses.append(data)

    # Verify
    mock_services["search"].search.assert_called_once()

    # Check sources
    sources_response = next((r for r in responses if r.get("type") == "sources"), None)
    assert sources_response is not None
    assert len(sources_response["sources"]) > 0
    assert sources_response["sources"][0]["id"] == "s1"
