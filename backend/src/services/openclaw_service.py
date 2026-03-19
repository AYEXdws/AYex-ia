from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from urllib import request as urlrequest

from backend.src.config.env import BackendSettings
from backend.src.services.http_utils import parse_json_bytes, with_retries


@dataclass
class OpenClawResult:
    ok: bool
    text: str
    raw: dict
    latency_ms: int = 0
    cache_hit: bool = False
    token_budget: int = 0
    context_messages: int = 0
    used_model: str = ""


class OpenClawService:
    def __init__(self, settings: BackendSettings):
        self.settings = settings
        self._cache: dict[str, tuple[float, OpenClawResult]] = {}
        self._cache_lock = threading.Lock()

    def is_enabled(self) -> bool:
        return self.settings.openclaw_enabled

    def run_action(
        self,
        text: str,
        workspace: str | None = None,
        model: str | None = None,
        history: list[dict[str, str]] | None = None,
        profile_context: str | None = None,
        memory_context: str | None = None,
    ) -> OpenClawResult:
        if not self.is_enabled():
            return OpenClawResult(ok=False, text="OpenClaw devre disi.", raw={})

        mode = self.settings.openclaw_mode
        if mode not in {"action", "openai_responses", "openai_chat_completions"}:
            return OpenClawResult(ok=False, text=f"OpenClaw mod gecersiz: {mode}", raw={})

        prompt = (text or "").strip()
        model_name = self._resolve_model(model)
        context = self._sanitize_history(history or [], max_turns=self.settings.openclaw_context_turns)
        context_messages = len(context)
        token_budget = self._compute_token_budget(prompt)
        system_prompt = self._compose_system_prompt(profile_context, memory_context)

        cache_key = self._cache_key(
            mode=mode,
            model=model_name,
            prompt=prompt,
            system_prompt=system_prompt,
            history=context,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        started = time.perf_counter()

        def _call() -> OpenClawResult:
            if mode == "openai_responses":
                req = urlrequest.Request(
                    f"{self.settings.openclaw_base_url}/v1/responses",
                    data=json.dumps(
                        {
                            "model": model_name,
                            "input": self._responses_input(prompt=prompt, history=context),
                            "instructions": system_prompt,
                            "max_output_tokens": token_budget,
                        }
                    ).encode("utf-8"),
                    method="POST",
                    headers=self._headers(),
                )
            elif mode == "openai_chat_completions":
                messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
                messages.extend(context)
                messages.append({"role": "user", "content": prompt})
                req = urlrequest.Request(
                    f"{self.settings.openclaw_base_url}/v1/chat/completions",
                    data=json.dumps(
                        {
                            "model": model_name,
                            "messages": messages,
                            "max_tokens": token_budget,
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
                            "text": prompt,
                            "workspace": workspace,
                            "model": model_name,
                            "instructions": system_prompt,
                            "history": context,
                        }
                    ).encode("utf-8"),
                    method="POST",
                    headers=self._headers(),
                )
            with urlrequest.urlopen(req, timeout=self.settings.openclaw_timeout_sec) as resp:
                data = parse_json_bytes(resp.read())
            text_out = self._extract_text(data)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return OpenClawResult(
                ok=True,
                text=text_out,
                raw=data,
                latency_ms=latency_ms,
                cache_hit=False,
                token_budget=token_budget,
                context_messages=context_messages,
                used_model=self._extract_used_model(data, fallback=model_name),
            )

        try:
            result = with_retries(_call, f"openclaw_{mode}", retries=0)
            self._cache_set(cache_key, result)
            return result
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return OpenClawResult(
                ok=False,
                text=self._friendly_error(str(exc)),
                raw={"error": str(exc), "mode": mode},
                latency_ms=latency_ms,
                cache_hit=False,
                token_budget=token_budget,
                context_messages=context_messages,
                used_model=model_name,
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
        if t.lower() in {"no response from openclaw.", "no response from model.", "no response", "no reply from agent."}:
            return "OpenClaw yanit uretemedi."
        return t

    def _friendly_error(self, err: str) -> str:
        low = err.lower()
        if "401" in low:
            return "Kimlik dogrulama hatasi (401). OpenAI/OpenClaw anahtarlarini kontrol et."
        if "timed out" in low or "timeout" in low:
            return "OpenClaw yaniti gecikti. Tekrar dene."
        if "connection refused" in low or "failed to establish" in low:
            return "OpenClaw servisine baglanilamadi. Gateway acik mi kontrol et."
        return "OpenClaw baglanti hatasi."

    def _responses_input(self, prompt: str, history: list[dict[str, str]]) -> str:
        if not history:
            return prompt
        lines: list[str] = []
        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            lines.append(f"{role}: {content}")
        lines.append(f"user: {prompt}")
        return "\n".join(lines)

    def _sanitize_history(self, history: list[dict[str, str]], max_turns: int) -> list[dict[str, str]]:
        if max_turns <= 0:
            return []
        clean: list[dict[str, str]] = []
        for item in history[-(max_turns * 2) :]:
            role = str(item.get("role") or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            clean.append({"role": role, "content": content[:2000]})
        return clean

    def _compose_system_prompt(self, profile_context: str | None, memory_context: str | None) -> str:
        base = self.settings.openclaw_instructions.strip()
        parts = [base]
        profile = (profile_context or "").strip()
        memory = (memory_context or "").strip()
        if profile:
            parts.append(f"Profil baglami: {profile[:1400]}")
        if memory:
            parts.append(
                "Kural: Eger uzun sureli sohbet baglaminda ilgili bir kayit varsa, "
                "once bunu acikca kullan; 'hatirlamiyorum' deme."
            )
            parts.append(f"Uzun sureli sohbet baglami: {memory[:1600]}")
        return "\n\n".join(parts)

    def _compute_token_budget(self, prompt: str) -> int:
        base = self.settings.openclaw_max_output_tokens
        words = len(prompt.split())
        if words <= 6:
            return max(56, min(96, base))
        if words <= 14:
            return max(72, min(120, base))
        if words >= 40:
            return min(260, max(base + 70, 150))
        if words >= 24:
            return min(220, max(base + 40, 120))
        return base

    def _cache_key(
        self,
        mode: str,
        model: str,
        prompt: str,
        system_prompt: str,
        history: list[dict[str, str]],
    ) -> str:
        history_blob = "\n".join([f"{m.get('role')}:{m.get('content')}" for m in history[-4:]])
        raw = f"{mode}|{model}|{system_prompt}|{history_blob}|{prompt.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> OpenClawResult | None:
        if self.settings.openclaw_cache_ttl_sec <= 0:
            return None
        now = time.time()
        with self._cache_lock:
            item = self._cache.get(key)
            if not item:
                return None
            ts, res = item
            if (now - ts) > self.settings.openclaw_cache_ttl_sec:
                self._cache.pop(key, None)
                return None
            return OpenClawResult(
                ok=res.ok,
                text=res.text,
                raw=res.raw,
                latency_ms=0,
                cache_hit=True,
                token_budget=res.token_budget,
                context_messages=res.context_messages,
                used_model=res.used_model,
            )

    def _cache_set(self, key: str, result: OpenClawResult) -> None:
        if self.settings.openclaw_cache_ttl_sec <= 0:
            return
        with self._cache_lock:
            if len(self._cache) >= self.settings.openclaw_cache_size:
                oldest = min(self._cache.items(), key=lambda x: x[1][0])[0]
                self._cache.pop(oldest, None)
            self._cache[key] = (time.time(), result)

    def _resolve_model(self, requested_model: str | None) -> str:
        configured = self.settings.openclaw_model.strip()
        if self.settings.openclaw_force_model:
            return configured
        return (requested_model or configured).strip()

    def _extract_used_model(self, raw: dict, fallback: str) -> str:
        val = raw.get("model")
        if isinstance(val, str) and val.strip():
            return val.strip()
        return fallback
