import json
import os
from typing import Any
from urllib import request as urlrequest

from .config import DEFAULT_OPENAI_BASE_URL


class OpenAIClient:
    def __init__(self, model: str, base_url: str = DEFAULT_OPENAI_BASE_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("AYEX_API_KEY") or "").strip()
        self.timeout_sec = int(os.environ.get("AYEX_OPENAI_TIMEOUT_SEC", "45"))

    def _extract_text(self, data: dict[str, Any]) -> str:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        chunks: list[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                if content.get("type") in {"output_text", "text"}:
                    text_value = content.get("text")
                    if isinstance(text_value, str):
                        chunks.append(text_value)
                    elif isinstance(text_value, dict):
                        value = text_value.get("value")
                        if isinstance(value, str):
                            chunks.append(value)
        if chunks:
            return "".join(chunks).strip()

        for choice in data.get("choices", []):
            if not isinstance(choice, dict):
                continue
            message = choice.get("message", {})
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return ""

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 128,
        allow_thinking: bool = False,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY veya AYEX_API_KEY tanimli degil.")

        payload: dict[str, Any] = {
            "model": self.model,
            "input": prompt,
            "store": False,
            "max_output_tokens": max_tokens,
        }
        if system:
            payload["instructions"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        if allow_thinking:
            payload["reasoning"] = {"effort": "medium"}

        body = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            f"{self.base_url}/responses",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urlrequest.urlopen(req, timeout=self.timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return self._extract_text(data)
