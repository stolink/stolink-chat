import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Adjust path to include app
sys.path.append(os.getcwd())

from app.services.chat_service import chat_service
from langchain.schema import HumanMessage, SystemMessage

async def mock_hybrid_search(project_id, query_embedding, neo4j_limit=None, postgres_limit=None):
    # Mock returning relevant context
    return [
        {
            "id": "chunk-1",
            "content": "Minjun is the main character of the novel.",
            "score": 0.9,
            "source": "neo4j",
            "source_type": "chunk"
        }
    ]

async def verify_guardrail():
    print("=== Verifying Guardrails ===")

    # Mock Redis Service
    with patch("app.services.chat_service.redis_service", new_callable=AsyncMock) as mock_redis:
        mock_redis.add_message_to_history.return_value = None
        mock_redis.get_session_history.return_value = []
        mock_redis.create_stop_listener.return_value = AsyncMock()
        mock_redis.create_stop_listener.return_value.get_message.return_value = None

        # Mock Embedding Service
        with patch("app.services.chat_service.embedding_service", new_callable=MagicMock) as mock_embed:
            mock_embed.get_embedding.return_value = [0.1] * 1536

            # Mock Unified Search Service
            with patch("app.services.chat_service.unified_search_service", new_callable=AsyncMock) as mock_search:
                mock_search.hybrid_search.side_effect = mock_hybrid_search

                # Mock LLM (ChatOpenAI)
                # We want to intercept the messages passed to the LLM to verify the System Prompt
                mock_llm = AsyncMock()
                # Create a mock async generator for astream
                async def async_generator(messages):
                    # Check System Prompt
                    system_msg = messages[0].content
                    print(f"\n[System Prompt Preview]:\n{system_msg[:300]}...\n")

                    if "cannot be answered using the Context" in system_msg:
                        print("[PASS] System Prompt contains refusal instruction.")
                    else:
                        print("[FAIL] System Prompt missing refusal instruction.")

                    if "Minjun is the main character" in system_msg:
                        print("[PASS] System Prompt contains retrieved context.")
                    else:
                        print("[FAIL] System Prompt missing context.")

                    # Simulate response
                    yield MagicMock(content="Minjun is the protagonist.")

                mock_llm.astream.side_effect = async_generator

                # Replace the LLM in chat_service
                chat_service.llm = mock_llm

                # Run Chat Stream
                print("\n[Running Chat Stream with 'Who is Minjun?']...")
                async for token in chat_service.chat_stream("Who is Minjun?", "proj-1", "sess-1"):
                    pass

if __name__ == "__main__":
    asyncio.run(verify_guardrail())
