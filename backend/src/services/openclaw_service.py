from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import request as urlrequest

from backend.src.config.env import BackendSettings
from backend.src.services.http_utils import parse_json_bytes, with_retries


@dataclass
class OpenClawResult:
    ok: bool
    text: str
    raw: dict


class OpenClawService:
    def __init__(self, settings: BackendSettings):
        self.settings = settings

    def is_enabled(self) -> bool:
        return self.settings.openclaw_enabled

    def run_action(self, text: str, workspace: str | None = None, model: str | None = None) -> OpenClawResult:
        if not self.is_enabled():
            return OpenClawResult(ok=False, text="OpenClaw devre disi.", raw={})

        mode = self.settings.openclaw_mode
        if mode not in {"action", "openai_responses", "openai_chat_completions"}:
            return OpenClawResult(ok=False, text=f"OpenClaw mod gecersiz: {mode}", raw={})

        def _call() -> OpenClawResult:
            if mode == "openai_responses":
                req = urlrequest.Request(
                    f"{self.settings.openclaw_base_url}/v1/responses",
                    data=json.dumps(
                        {
                            "model": model or self.settings.openclaw_model,
                            "input": text,
                            "instructions": self.settings.openclaw_instructions,
                            "max_output_tokens": self.settings.openclaw_max_output_tokens,
                        }
                    ).encode("utf-8"),
                    method="POST",
                    headers=self._headers(),
                )
            elif mode == "openai_chat_completions":
                req = urlrequest.Request(
                    f"{self.settings.openclaw_base_url}/v1/chat/completions",
                    data=json.dumps(
                        {
                            "model": model or self.settings.openclaw_model,
                            "messages": [
                                {"role": "system", "content": self.settings.openclaw_instructions},
                                {"role": "user", "content": text},
                            ],
                            "max_tokens": self.settings.openclaw_max_output_tokens,
                            "temperature": 0.2,
                        }
                    ).encode("utf-8"),
                    method="POST",
                    headers=self._headers(),
                )
            else:
                path = self.settings.openclaw_action_path or "/action"
                if not path.startswith("/"):
                    path = f"/{path}"
                req = urlrequest.Request(
                    f"{self.settings.openclaw_base_url}{path}",
                    data=json.dumps(
                        {
                            "text": text,
                            "workspace": workspace,
                            "model": model,
                            "instructions": self.settings.openclaw_instructions,
                        }
                    ).encode("utf-8"),
                    method="POST",
                    headers=self._headers(),
                )
            with urlrequest.urlopen(req, timeout=15) as resp:
                data = parse_json_bytes(resp.read())
            text_out = self._extract_text(data)
            return OpenClawResult(ok=True, text=text_out, raw=data)

        try:
            return with_retries(_call, f"openclaw_{mode}", retries=0)
        except Exception as exc:
            return OpenClawResult(
                ok=False,
                text="OpenClaw baglanti hatasi.",
                raw={"error": str(exc), "mode": mode},
            )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.openclaw_api_key:
            headers["Authorization"] = f"Bearer {self.settings.openclaw_api_key}"
        return headers

    def _extract_text(self, data: dict) -> str:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            text = output_text.strip()
            return self._localize_fallback(text)
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        return self._localize_fallback(content.strip())
        for key in ("reply", "text", "message", "output"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return self._localize_fallback(val.strip())
        out = data.get("output")
        if isinstance(out, list):
            chunks: list[str] = []
            for item in out:
                if not isinstance(item, dict):
                    continue
                for content in item.get("content", []):
                    if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                        text = content.get("text")
                        if isinstance(text, str):
                            chunks.append(text)
            if chunks:
                return self._localize_fallback("".join(chunks).strip())
        return "OpenClaw islem tamamladi."

    def _localize_fallback(self, text: str) -> str:
        t = text.strip()
        if t.lower() in {"no response from openclaw.", "no response from model.", "no response"}:
            return "OpenClaw yanit uretemedi."
        return t
