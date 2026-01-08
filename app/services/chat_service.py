from app.services.embedding_service import embedding_service
from app.services.unified_search_service import unified_search_service
from app.services.redis_service import redis_service
from app.config import settings
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from typing import AsyncGenerator, Dict, Any, List
import json
import asyncio


class ChatService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=settings.OPENAI_API_KEY,
            streaming=True
        )

    def _format_context(self, results: List[Dict[str, Any]]) -> str:
        """검색 결과를 프롬프트용 컨텍스트로 포맷"""
        formatted = []
        for i, r in enumerate(results, 1):
            source_label = f"[{r['source'].upper()}:{r['source_type']}]"
            score_label = f"(similarity: {r['score']:.3f})"
            formatted.append(f"{i}. {source_label} {score_label}\n{r['content']}")

        return "\n\n".join(formatted)

    async def chat_stream(
        self,
        message: str,
        project_id: str,
        session_id: str
    ) -> AsyncGenerator[str, None]:
        # 0. Save User Message to History
        await redis_service.add_message_to_history(session_id, "user", message)

        # 0.5 Intent Classification (Layer 2 Guardrail)
        intent_prompt = [
            SystemMessage(content="""You are an intent classifier for a novel chatbot.
Classify if the user's query is related to the novel (plot, characters, setting, or casual greeting) or if it is Out-of-Domain (general knowledge, coding, math, real-world news).
Reply with 'Y' if related/safe, 'N' if Out-of-Domain.
"""),
            HumanMessage(content=message)
        ]
        intent_check = await self.llm.ainvoke(intent_prompt)
        if intent_check.content.strip().upper().startswith('N'):
            refusal_msg = "I can only answer questions related to the novel story."
            yield f"data: {json.dumps({'type': 'token', 'content': refusal_msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            await redis_service.add_message_to_history(session_id, "ai", refusal_msg)
            return

        # 1. Embed Query (비동기 래핑)
        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(
            None,
            embedding_service.get_embedding,
            message
        )

        # 2. Retrieve Context (Neo4j + PostgreSQL 통합 검색)
        context_results = await unified_search_service.hybrid_search(
            project_id=project_id,
            query_embedding=query_embedding
        )

        # 3. Format Context (소스 타입 포함)
        context_text = self._format_context(context_results)

        # Send sources first (소스 정보 포함)
        sources_data = {
            "type": "sources",
            "sources": [
                {
                    "id": c["id"],
                    "content": c["content"][:200] + "..." if len(c["content"]) > 200 else c["content"],
                    "score": round(c["score"], 4),
                    "source": c["source"],
                    "source_type": c["source_type"]
                }
                for c in context_results
            ]
        }
        yield f"data: {json.dumps(sources_data)}\n\n"

        # 4. Construct Prompt
        system_prompt = f"""You are a dedicated AI assistant for a specific novel project.
Your goal is to assist the user based ONLY on the provided context from the novel.

Guidelines:
1. Answer ONLY using the information present in the Context below.
2. If the user asks a question that cannot be answered using the Context (e.g., general knowledge, real-world events, or details not in the story), you MUST politely refuse.
3. Do not make up facts or hallucinate details not in the source text.

Examples:
User: "What is the capital of France?"
AI: "I can only answer questions related to the story content provided."

User: "Who is the main character?" (Context contains Minjun)
AI: "The main character is Minjun, a 25-year-old computer engineering graduate."

User: "Write python code for a snake game."
AI: "I can only answer questions related to the story content provided."

Context:
{context_text}
"""

        messages = [SystemMessage(content=system_prompt)]

        # 5. Retrieve History from Redis
        history = await redis_service.get_session_history(session_id)
        # Filter out the current message we just added (if desired, or just use all except last? No, we need it)
        # Actually, we just added it. So it IS in history.
        # But we need to construct the message list for the LLM.
        # We can just fetch all history.

        # Note: History in Redis is [{"role": "user", "content": "..."}, ...]
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                messages.append(AIMessage(content=msg["content"]))

        # Setup Stop Listener
        pubsub = await redis_service.create_stop_listener(session_id)

        full_response = ""

        # 6. Generate Streaming Response
        try:
            async for chunk in self.llm.astream(messages):
                # Check for stop signal
                msg = await pubsub.get_message(ignore_subscribe_messages=True)
                if msg and msg['data'] == 'STOP':
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Generation stopped by user'})}\n\n"
                    full_response = "" # Or keep partial? Let's treat as cancelled.
                    # If cancelled, do we save partial? Maybe not.
                    break

                if chunk.content:
                    token_data = {
                        "type": "token",
                        "content": chunk.content
                    }
                    yield f"data: {json.dumps(token_data)}\n\n"
                    full_response += chunk.content

            # Done signal
            if full_response:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                # Save AI Message to History
                await redis_service.add_message_to_history(session_id, "ai", full_response)

        except Exception as e:
            error_data = {
                "type": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            await pubsub.close()

chat_service = ChatService()
