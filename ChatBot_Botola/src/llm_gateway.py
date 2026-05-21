# chatbot-service/src/llm_gateway.py
"""
Unified LLM interface for Ollama, Mistral, and OpenRouter.

Improvements over v1:
- Uses proper chat-messages format for all providers (system / user / assistant turns)
  instead of a monolithic string template with fragile string-split.
- Conversation history is injected as real alternating turns, not a raw text block.
- Supports token streaming (yield tokens as they arrive) for real-time UX.
- Structured logging replaces print() calls.
"""
import json
from typing import AsyncGenerator, Dict, List, Optional
from dataclasses import dataclass

import httpx

from .config import (
    LLM_PROVIDER, OLLAMA_URL, OLLAMA_MODEL,
    MISTRAL_API_KEY, MISTRAL_MODEL,
    OPENROUTER_API_KEY, OPENROUTER_MODEL,
    MAX_TOKENS, TEMPERATURE,
)
from .logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    text: str
    tokens_used: int = 0
    model: str = ""
    finish_reason: str = ""


# ---------------------------------------------------------------------------
# System prompt (instructions only — no context/history baked in)
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTIONS = """\
You are Botola Pro AI, the official intelligent assistant for Moroccan football ticketing.

CORE RULES:
1. Answer ONLY using the provided context. If information is missing, say "I don't have that information. Please contact Botola Pro support."
2. Be concise (2-3 sentences max for simple questions).
3. For ticket/seat queries, include specific details (zone, row, seat number) from the context.
4. For security questions, emphasize Botola Pro's verification systems.
5. NEVER generate fake ticket IDs, seat numbers, or prices not present in the context.
6. If the user asks about betting, gambling, or odds, politely refuse.
7. Respond in the SAME language as the user's query (EN / FR / AR / Darija).
8. For Arabic responses, use clear Modern Standard Arabic unless the user wrote in Darija.
"""


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class LLMGateway:
    """
    Unified interface for multiple LLM providers.
    Supports: Ollama (local), Mistral API, OpenRouter.
    """

    def __init__(self):
        self.provider = LLM_PROVIDER
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info("LLM Gateway initialised", extra={"provider": self.provider})

    # ------------------------------------------------------------------
    # Public: full response
    # ------------------------------------------------------------------

    async def generate(
        self,
        query: str,
        context: str,
        history: List[Dict],     # list of {"role": "user"|"assistant", "content": str}
        language: str = "en",
    ) -> LLMResponse:
        """
        Generate a full (non-streaming) response.

        Args:
            query:    Current user message.
            context:  Retrieved RAG context or formatted DB result.
            history:  Previous conversation turns as chat messages.
            language: Detected language code (for logging).
        """
        messages = self._build_messages(query, context, history)

        if self.provider == "ollama":
            return await self._call_ollama(messages)
        elif self.provider == "mistral":
            return await self._call_mistral(messages)
        elif self.provider == "openrouter":
            return await self._call_openrouter(messages)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider!r}")

    # ------------------------------------------------------------------
    # Public: streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        query: str,
        context: str,
        history: List[Dict],
        language: str = "en",
    ) -> AsyncGenerator[str, None]:
        """
        Stream response tokens as they arrive.
        Yields individual token strings.
        """
        messages = self._build_messages(query, context, history)

        if self.provider == "ollama":
            async for token in self._stream_ollama(messages):
                yield token
        elif self.provider == "mistral":
            async for token in self._stream_mistral(messages):
                yield token
        elif self.provider == "openrouter":
            async for token in self._stream_openrouter(messages):
                yield token
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider!r}")

    # ------------------------------------------------------------------
    # Message builder (shared by all providers)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(
        query: str,
        context: str,
        history: List[Dict],
    ) -> List[Dict]:
        """
        Build the chat messages list:
          [system] instructions
          [user/assistant] ... history turns ...
          [user] context + current question
        """
        messages: List[Dict] = [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        ]

        # Inject history as real alternating turns
        for turn in history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # Final user turn: context + question
        user_content = (
            f"CONTEXT:\n{context}\n\nQUESTION: {query}"
            if context
            else f"QUESTION: {query}"
        )
        messages.append({"role": "user", "content": user_content})
        return messages

    # ------------------------------------------------------------------
    # Ollama
    # ------------------------------------------------------------------

    async def _call_ollama(self, messages: List[Dict]) -> LLMResponse:
        """Call local Ollama chat endpoint."""
        url = f"{OLLAMA_URL}/api/chat"
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": MAX_TOKENS,
            },
        }
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            text=data.get("message", {}).get("content", "").strip(),
            tokens_used=data.get("eval_count", 0),
            model=OLLAMA_MODEL,
            finish_reason="stop",
        )

    async def _stream_ollama(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        url = f"{OLLAMA_URL}/api/chat"
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": True,
            "options": {"temperature": TEMPERATURE, "num_predict": MAX_TOKENS},
        }
        async with self.client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

    # ------------------------------------------------------------------
    # Mistral API
    # ------------------------------------------------------------------

    async def _call_mistral(self, messages: List[Dict]) -> LLMResponse:
        """Call Mistral chat completions API with proper message format."""
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": MISTRAL_MODEL,
            "messages": messages,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
        }
        response = await self.client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        return LLMResponse(
            text=choice["message"]["content"].strip(),
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            model=MISTRAL_MODEL,
            finish_reason=choice.get("finish_reason", ""),
        )

    async def _stream_mistral(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": MISTRAL_MODEL,
            "messages": messages,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "stream": True,
        }
        async with self.client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    raw = line[6:]
                    if raw.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                        delta = data["choices"][0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue

    # ------------------------------------------------------------------
    # OpenRouter
    # ------------------------------------------------------------------

    async def _call_openrouter(self, messages: List[Dict]) -> LLMResponse:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://botolapro.com",
            "X-Title": "Botola Pro Chatbot",
        }
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
        }
        response = await self.client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        return LLMResponse(
            text=choice["message"]["content"].strip(),
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            model=OPENROUTER_MODEL,
            finish_reason=choice.get("finish_reason", ""),
        )

    async def _stream_openrouter(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://botolapro.com",
            "X-Title": "Botola Pro Chatbot",
        }
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "stream": True,
        }
        async with self.client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    raw = line[6:]
                    if raw.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                        delta = data["choices"][0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self):
        await self.client.aclose()


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    async def test():
        gateway = LLMGateway()

        context = "Gates open 2 hours before kick-off. Bags must be smaller than 30x30x15cm."
        query = "Can I bring a backpack?"
        history = []

        response = await gateway.generate(query, context, history, language="en")
        print(f"\nResponse: {response.text}")
        print(f"Tokens:   {response.tokens_used}")
        print(f"Model:    {response.model}")

        await gateway.close()

    asyncio.run(test())