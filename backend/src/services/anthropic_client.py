"""Anthropic Claude API client for AYEX-IA."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class ClaudeChatResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class AnthropicClient:
    """Thin wrapper around the Anthropic Python SDK."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> ClaudeChatResult:
        """Send a chat request to Claude."""
        t0 = time.perf_counter()

        api_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                if not system:
                    system = content
                continue
            if role not in ("user", "assistant"):
                role = "user"
            api_messages.append({"role": role, "content": content})

        if api_messages and api_messages[0]["role"] == "assistant":
            api_messages.insert(0, {"role": "user", "content": "."})

        merged = []
        for msg in api_messages:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n" + msg["content"]
            else:
                merged.append(msg)
        api_messages = merged

        if api_messages and api_messages[-1]["role"] != "user":
            api_messages.append({"role": "user", "content": "."})

        if not api_messages:
            api_messages = [{"role": "user", "content": "."}]

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system if system else "",
                messages=api_messages,
            )

            latency = int((time.perf_counter() - t0) * 1000)
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            logger.info(
                "CLAUDE_CALL_SUCCESS model=%s latency_ms=%d input_tokens=%d output_tokens=%d",
                response.model,
                latency,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

            return ClaudeChatResult(
                text=text,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=latency,
            )
        except anthropic.APIError as e:
            latency = int((time.perf_counter() - t0) * 1000)
            logger.error("CLAUDE_CALL_FAILED error=%s latency_ms=%d", str(e), latency)
            raise
