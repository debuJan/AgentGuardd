"""
LLM provider abstraction.

Provides a common chat interface for AgentRunner while keeping
the provider-specific implementation inside this module.
"""
from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    latency_ms: float
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    model: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class LLMProvider(ABC):
    """Common interface every LLM backend must implement."""

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        ...


class GroqProvider(LLMProvider):
    """Groq chat completion provider."""

    def __init__(
        self,
        model_name: str = "llama-3.1-8b-instant",
        temperature: float = 0.1,
        max_tokens: int = 1024,
        api_key: Optional[str] = None,
    ):
        from langchain_groq import ChatGroq

        api_key = api_key or os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("GROQ_API_KEY missing! Set it in your .env file.")

        self.model_name = model_name

        self._client = ChatGroq(
            groq_api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        logger.info("Groq LLM initialized: %s", model_name)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:

        start = time.perf_counter()

        client = self._client

        # Bind tools only when tools are available.
        if tools:
            client = client.bind_tools(tools)

        result = client.invoke(messages)

        latency_ms = (time.perf_counter() - start) * 1000

        metadata = getattr(result, "response_metadata", {}) or {}
        usage = metadata.get("token_usage", {}) or {}

        raw_tool_calls = getattr(result, "tool_calls", None) or []

        tool_calls = []

        for call in raw_tool_calls:
            tool_calls.append(
                {
                    "name": call.get("name"),
                    "arguments": call.get("args", {}),
                }
            )

        return LLMResponse(
            content=result.content or "",
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            model=self.model_name,
            tool_calls=tool_calls,
        )


def get_llm_provider(
    provider: str = "groq",
    **kwargs,
) -> LLMProvider:

    providers = {
        "groq": GroqProvider,
    }

    if provider not in providers:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Available: {list(providers)}"
        )

    return providers[provider](**kwargs)