from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib import request as urlrequest

from backend.src.config.env import BackendSettings, openai_api_key
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OpenAIChatResult:
    text: str
    used_model: str
    latency_ms: int
    raw: dict[str, Any]


class OpenAIDirectClient:
    """Strict OpenAI caller for backend chat/action.

    This client intentionally does not emit canned responses. Callers must handle
    exceptions and map them to explicit user-facing errors.
    """

    def __init__(self, settings: BackendSettings):
        self.settings = settings
        self.base_url = settings.api_base_url.rstrip("/")

    def call_responses(
        self,
        *,
        prompt: str,
        model: str,
        instructions: str,
        max_output_tokens: int,
        route_name: str,
    ) -> OpenAIChatResult:
        started = time.perf_counter()

        logger.info(
            "OPENAI_CALL_START route=%s model=%s openclaw_enabled=%s",
            route_name,
            model,
            self.settings.openclaw_enabled,
        )

        payload: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "instructions": instructions,
            "max_output_tokens": max_output_tokens,
            "store": False,
            "temperature": 0.2,
        }
        try:
            api_key = openai_api_key()
            req = urlrequest.Request(
                f"{self.base_url}/responses",
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urlrequest.urlopen(req, timeout=self.settings.openai_timeout_sec) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            text = self._extract_text(raw).strip()
            if not text:
                raise RuntimeError("Empty model text")
            latency_ms = int((time.perf_counter() - started) * 1000)
            used_model = self._extract_model(raw, model)
            logger.info(
                "OPENAI_CALL_SUCCESS route=%s model=%s latency_ms=%s",
                route_name,
                used_model,
                latency_ms,
            )
            return OpenAIChatResult(
                text=text,
                used_model=used_model,
                latency_ms=latency_ms,
                raw=raw,
            )
        except Exception as exc:
            logger.error(
                "OPENAI_CALL_ERROR route=%s model=%s error=%s",
                route_name,
                model,
                exc,
            )
            raise

    def _extract_model(self, raw: dict[str, Any], fallback: str) -> str:
        model = raw.get("model")
        if isinstance(model, str) and model.strip():
            return model.strip()
        return fallback

    def _extract_text(self, raw: dict[str, Any]) -> str:
        output_text = raw.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = raw.get("output")
        if isinstance(output, list):
            chunks: list[str] = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                content_list = item.get("content")
                if not isinstance(content_list, list):
                    continue
                for content in content_list:
                    if not isinstance(content, dict):
                        continue
                    if content.get("type") in {"output_text", "text"}:
                        txt = content.get("text")
                        if isinstance(txt, str):
                            chunks.append(txt)
            if chunks:
                return "".join(chunks).strip()

        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str):
                        return content.strip()
        return ""
