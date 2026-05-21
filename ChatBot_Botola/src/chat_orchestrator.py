# chatbot-service/src/chat_orchestrator.py
"""
Full chatbot orchestrator with:
- Query rewriting using conversation history (contextual RAG)
- Embedding-based intent classification
- Hybrid RAG retrieval + cross-encoder reranking
- Proper chat-messages format for LLM (no monolithic prompt)
- Structured logging
"""
import asyncio
import time
from typing import Dict, List, Optional

from .config import STATIC_INTENTS, DYNAMIC_INTENTS, REDIS_URL
from .intent_classifier import IntentClassifier
from .rag_engine import RAGEngine
from .query_builder import QueryBuilder
from .response_formatter import ResponseFormatter
from .memory import ConversationMemory
from .llm_gateway import LLMGateway
from .guardrails import Guardrails
from .action_router import ActionRouter
from .logger import get_logger

logger = get_logger(__name__)


class ChatOrchestrator:
    """
    Full chatbot orchestrator with LLM, memory, guardrails, and action routing.
    """

    def __init__(self):
        self.classifier = IntentClassifier()
        self.rag = RAGEngine()
        self.query_builder = QueryBuilder()
        self.formatter = ResponseFormatter()
        self.memory = ConversationMemory(REDIS_URL)
        self.llm = LLMGateway()
        self.guardrails = Guardrails()
        self.router = ActionRouter()

        # Initialise RAG index
        if self.rag._index_exists():
            self.rag.load()
        else:
            from main import _create_sample_documents
            _create_sample_documents()
            self.rag.build()

        logger.info("Chat Orchestrator fully initialised")

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    async def process(
        self,
        user_id: str,
        session_id: str,
        message: str,
        language: str = "auto",
    ) -> Dict:
        """
        Process a user message through the complete pipeline:
          1. Input guardrails
          2. Retrieve conversation history
          3. Query rewriting (contextual RAG)
          4. Intent classification
          5. Route: static (RAG) | dynamic (DB) | unknown (fallback)
          6. LLM generation with proper chat messages
          7. Output guardrails
          8. Action routing
          9. Persist to memory
        """
        start_time = time.time()

        # ── Step 1: Input safety check ─────────────────────────────────
        safety = self.guardrails.check_input(message, user_id)
        if not safety.passed:
            processing_time = round((time.time() - start_time) * 1000)
            logger.warning("Input blocked by guardrails", extra={
                "user_id": user_id, "reason": safety.reason
            })
            return self._build_response(
                type="chat_reply",
                message="I can't help with that. For assistance, contact Botola Pro support.",
                metadata={
                    "intent": "blocked_by_guardrails",
                    "route": "security",
                    "confidence": 1.0,
                    "processing_time_ms": processing_time,
                    "blocked": True,
                    "reason": safety.reason,
                },
            )

        # ── Step 2: Retrieve conversation history ──────────────────────
        history_turns = self.memory.get_history(session_id)       # raw turns for LLM
        history_text = self.memory.get_formatted_history(session_id)  # for logging

        # ── Step 3: Query rewriting for contextual RAG ─────────────────
        # Combine recent user turns with the current message so RAG can
        # resolve pronouns and implicit references.
        # e.g. "What about backpacks?" after "Can I bring a bag?"
        contextual_query = self._rewrite_query(message, history_turns)

        # ── Step 4: Classify intent ────────────────────────────────────
        classification = self.classifier.classify(message)  # classify original (not rewritten)
        intent = classification["intent"]
        route = classification["route"]
        detected_lang = classification["language"] if language == "auto" else language

        # ── Step 5: Route to appropriate data pipeline ─────────────────
        context_str = ""
        db_data: Dict = {}
        sources: List[str] = []

        if route == "static":
            rag_result = self.rag.answer(contextual_query)
            if rag_result["has_context"]:
                context_str = f"STADIUM DOCUMENTS:\n{rag_result['context']}"
                sources = rag_result["sources"]
            else:
                # No relevant docs found — let LLM say so honestly
                context_str = ""
                sources = []
            has_seat_data = False

        elif route == "dynamic":
            db_result = self.query_builder.build_and_execute(intent, message, user_id)
            db_data = db_result
            formatted = self.formatter.format(db_result, detected_lang)
            context_str = f"LIVE DATABASE RESULT:\n{formatted}"
            sources = ["live_db"]
            has_seat_data = db_result.get("type") == "seat_info"

        else:
            # Unknown intent — try RAG as best-effort fallback
            rag_result = self.rag.answer(contextual_query)
            if rag_result["has_context"]:
                context_str = f"STADIUM DOCUMENTS (FALLBACK):\n{rag_result['context']}"
                sources = rag_result["sources"]
            has_seat_data = False

        # ── Step 6: Generate LLM response ──────────────────────────────
        # Convert memory turns to proper chat message dicts for the LLM
        llm_history = self._history_to_messages(history_turns)

        llm_response = None
        try:
            llm_response = await self.llm.generate(
                query=message,
                context=context_str,
                history=llm_history,
                language=detected_lang,
            )
            response_text = llm_response.text

            # Apply output guardrails
            output_safety = self.guardrails.check_output(response_text, {
                "route": route,
                "db_verified": route == "dynamic",
                "has_seat_data": has_seat_data,
            })

            if not output_safety.passed:
                if output_safety.action == "escalate":
                    response_text = (
                        "I'm not sure about that. Let me connect you with a support agent."
                    )
                else:
                    response_text = (
                        "I apologize, but I need to verify that information. "
                        "Please check the Botola Pro app for the most current details."
                    )

            response_text = self.guardrails.sanitize_output(response_text)

        except Exception as exc:
            logger.error("LLM generation failed", extra={"error": str(exc)})
            # Graceful fallback: return the formatted DB/RAG data directly
            response_text = (
                db_data.get("formatted_response")
                or context_str
                or "I'm having trouble generating a response. Please try again."
            )

        # ── Step 7: Route to action ────────────────────────────────────
        action_data = {"formatted_response": response_text, **db_data}
        action = self.router.route(intent, action_data, classification["confidence"])
        frontend_action = self.router.format_for_frontend(action)

        # ── Step 8: Save to memory ─────────────────────────────────────
        self.memory.add_turn(session_id, "user", message, {"intent": intent})
        self.memory.add_turn(session_id, "assistant", response_text, {"action": action["type"]})

        # ── Step 9: Build final response ───────────────────────────────
        processing_time = round((time.time() - start_time) * 1000)

        logger.info("Chat request processed", extra={
            "user_id": user_id,
            "session_id": session_id,
            "intent": intent,
            "route": route,
            "confidence": classification["confidence"],
            "language": detected_lang,
            "rag_chunks": len(
                rag_result.get("chunks", []) if route in ("static", "unknown") and "rag_result" in dir() else []
            ),
            "processing_ms": processing_time,
        })

        return {
            "type": frontend_action["type"],
            "message": frontend_action["message"],
            "data": frontend_action["data"],
            "actions": frontend_action["actions"],
            "sources": sources,
            "metadata": {
                "intent": intent,
                "confidence": classification["confidence"],
                "language": detected_lang,
                "route": route,
                "processing_time_ms": processing_time,
                "llm_tokens": getattr(llm_response, "tokens_used", 0),
            },
        }

    # ------------------------------------------------------------------
    # Query rewriting
    # ------------------------------------------------------------------

    @staticmethod
    def _rewrite_query(current_message: str, history_turns: List[Dict]) -> str:
        """
        Create a context-enriched query for RAG by prepending recent
        user messages so that pronoun references can be resolved.

        E.g.:
          history: "Can I bring a bag?"
          current: "What about backpacks?"
          rewritten: "Can I bring a bag? What about backpacks?"

        This is a lightweight rule-based rewrite (no extra LLM call).
        For production, replace with an LLM-based query rewriter.
        """
        recent_user_msgs = [
            t["content"]
            for t in history_turns[-4:]  # last 2 turns (user + assistant × 2)
            if t.get("role") == "user"
        ][-2:]  # at most 2 previous user queries

        if not recent_user_msgs:
            return current_message

        context_prefix = " ".join(recent_user_msgs)
        return f"{context_prefix} {current_message}"

    # ------------------------------------------------------------------
    # History → LLM messages
    # ------------------------------------------------------------------

    @staticmethod
    def _history_to_messages(history_turns: List[Dict]) -> List[Dict]:
        """
        Convert raw memory turns to the {"role": ..., "content": ...}
        format expected by LLMGateway.generate().
        """
        messages = []
        for turn in history_turns:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        return messages

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_response(self, **kwargs) -> Dict:
        """Helper to build a consistent response dict."""
        return {
            "type": kwargs.get("type", "chat_reply"),
            "message": kwargs.get("message", ""),
            "data": kwargs.get("data", {}),
            "actions": kwargs.get("actions", []),
            "sources": kwargs.get("sources", []),
            "metadata": kwargs.get("metadata", {}),
        }

    async def close(self):
        """Cleanup resources."""
        await self.llm.close()


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    async def test():
        orchestrator = ChatOrchestrator()

        test_queries = [
            ("u_buyer_001", "s1", "Can I bring a backpack to the stadium?", "en"),
            ("u_buyer_001", "s1", "What about a camera bag?", "en"),   # contextual follow-up
            ("u_buyer_001", "s1", "Where is my seat for Raja vs MAS?", "en"),
            ("u_buyer_001", "s1", "What are the betting odds?", "en"),
            ("u_buyer_001", "s2", "Show my tickets", "en"),
        ]

        for uid, sid, msg, lang in test_queries:
            print(f"\n{'='*60}")
            print(f"Query: {msg}")
            result = await orchestrator.process(uid, sid, msg, lang)
            print(f"Intent: {result['metadata']['intent']} ({result['metadata']['route']})")
            print(f"Response: {result['message'][:200]}")
            print(f"Actions: {[a['label'] for a in result['actions']]}")

        await orchestrator.close()

    asyncio.run(test())