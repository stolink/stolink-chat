import json
import redis.asyncio as redis
from app.config import settings
from typing import List, Dict, Optional

class RedisService:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.client = redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
        # Key Schema:
        # History: session:{session_id}:history (List of JSON)
        # Pub/Sub: control:{session_id} (Channel)

    async def add_message_to_history(self, session_id: str, role: str, content: str):
        """
        Appends a message to the session history.
        """
        key = f"session:{session_id}:history"
        message = {"role": role, "content": content}
        await self.client.rpush(key, json.dumps(message))
        # Optional: Set TTL (e.g., 7 days)
        await self.client.expire(key, 60 * 60 * 24 * 7)

    async def get_session_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Retrieves the full chat history for a session.
        """
        key = f"session:{session_id}:history"
        # Get all elements
        messages = await self.client.lrange(key, 0, -1)
        return [json.loads(msg) for msg in messages]

    async def publish_stop_signal(self, session_id: str):
        """
        Publishes a STOP signal to the session's control channel.
        """
        channel = f"control:{session_id}"
        await self.client.publish(channel, "STOP")

    async def create_stop_listener(self, session_id: str) -> redis.client.PubSub:
        """
        Creates and subscribes to a Pub/Sub listener for the session.
        """
        pubsub = self.client.pubsub()
        channel = f"control:{session_id}"
        await pubsub.subscribe(channel)
        return pubsub

    async def close(self):
        await self.client.close()

redis_service = RedisService()
