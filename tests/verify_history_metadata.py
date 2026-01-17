import asyncio
import json
from app.services.redis_service import redis_service

async def verify_history():
    session_id = "test-session-persistence"
    role = "ai"
    content = "This is a test message with cards."
    metadata = {
        "cards": [
            {
                "cardType": "relationship",
                "data": {"source": "A", "target": "B", "types": ["friend"]}
            }
        ],
        "sources": [{"content": "source text"}]
    }

    print(f"Adding message to {session_id}...")
    await redis_service.add_message_to_history(session_id, role, content, metadata=metadata)

    print("Retrieving history...")
    history = await redis_service.get_session_history(session_id, limit=1)

    if history:
        msg = history[0]
        print("Retrieved Message:", json.dumps(msg, indent=2))
        if "metadata" in msg and msg["metadata"]["cards"][0]["cardType"] == "relationship":
            print("SUCCESS: Metadata correctly persisted in Redis.")
        else:
            print("FAILURE: Metadata missing or incorrect.")
    else:
        print("FAILURE: No history found.")

    # Clean up
    await redis_service.client.delete(f"session:{session_id}:history")
    await redis_service.close()

if __name__ == "__main__":
    asyncio.run(verify_history())
