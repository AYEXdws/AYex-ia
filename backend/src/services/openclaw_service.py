from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from urllib import request as urlrequest

from backend.src.config.env import BackendSettings, normalize_model_for_openai
from backend.src.services.agent_registry import AgentRegistry
from backend.src.services.anthropic_client import AnthropicClient, ClaudeChatResult
from backend.src.services.http_utils import parse_json_bytes, with_retries
from backend.src.services.openai_client import OpenAIDirectClient
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OpenClawResult:
    ok: bool
    text: str
    raw: dict
    source: str = "openclaw"
    latency_ms: int = 0
    cache_hit: bool = False
    token_budget: int = 0
    context_messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    used_model: str = ""
    model_locked: bool = False
    response_style: str = "normal"


class OpenClawService:
    def __init__(self, settings: BackendSettings, agents: AgentRegistry, anthropic_client: AnthropicClient | None = None):
        self.settings = settings
        self.agents = agents
        self.openai = OpenAIDirectClient(settings)
        self.anthropic_client = anthropic_client
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
        response_style: str = "normal",
        route_name: str = "action",
    ) -> OpenClawResult:
        if not self.is_enabled():
            logger.info("ROUTE_SELECTED=openai_direct route=%s", route_name)
            return self._run_direct_openai(
                text=text,
                workspace=workspace,
                model=model,
                history=history,
                profile_context=profile_context,
                memory_context=memory_context,
                response_style=response_style,
                route_name=route_name,
            )

        logger.info("ROUTE_SELECTED=openclaw route=%s", route_name)
        mode = self.settings.openclaw_mode
        if mode not in {"action", "openai_responses", "openai_chat_completions"}:
            return OpenClawResult(ok=False, text=f"OpenClaw mod gecersiz: {mode}", raw={})

        prompt = (text or "").strip()
        model_name = self._resolve_model(model)
        context = self._sanitize_history(history or [], max_turns=self.settings.openclaw_context_turns)
        context_messages = len(context)
        token_budget = self._compute_token_budget(prompt, response_style=response_style)
        system_prompt = self._compose_system_prompt(profile_context, memory_context, response_style=response_style)

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
                normalized_model = normalize_model_for_openai(model_name)
                call_params: dict[str, object] = {
                    "model": model_name,
                    "messages": messages,
                    "max_tokens": token_budget,
                    "temperature": 0.2,
                }
                if "gpt-5" in (normalized_model or "").lower():
                    call_params.pop("temperature", None)
                req = urlrequest.Request(
                    f"{self.settings.openclaw_base_url}/v1/chat/completions",
                    data=json.dumps(call_params).encode("utf-8"),
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
            if not text_out:
                raise RuntimeError("OpenClaw returned empty model text")
            latency_ms = int((time.perf_counter() - started) * 1000)
            return OpenClawResult(
                ok=True,
                text=text_out,
                raw=data,
                source="openclaw",
                latency_ms=latency_ms,
                cache_hit=False,
                token_budget=token_budget,
                context_messages=context_messages,
                used_model=self._extract_used_model(data, fallback=model_name),
                model_locked=self.settings.openclaw_force_model,
                response_style=response_style,
            )

        try:
            result = with_retries(_call, f"openclaw_{mode}", retries=0)
            self._cache_set(cache_key, result)
            return result
        except Exception as exc:
            logger.error("OPENCLAW_CALL_ERROR route=%s mode=%s error=%s", route_name, mode, exc)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return OpenClawResult(
                ok=False,
                text=self._friendly_error(str(exc)),
                raw={"error": str(exc), "mode": mode},
                source="openclaw",
                latency_ms=latency_ms,
                cache_hit=False,
                token_budget=token_budget,
                context_messages=context_messages,
                used_model=model_name,
                model_locked=self.settings.openclaw_force_model,
                response_style=response_style,
            )

    def _run_direct_openai(
        self,
        text: str,
        workspace: str | None = None,
        model: str | None = None,
        history: list[dict[str, str]] | None = None,
        profile_context: str | None = None,
        memory_context: str | None = None,
        response_style: str = "normal",
        route_name: str = "action",
    ) -> OpenClawResult:
        _ = workspace
        prompt = (text or "").strip()
        model_name = self._resolve_model(model)
        normalized_model = normalize_model_for_openai(model_name)
        token_budget = self._compute_token_budget(prompt, response_style=response_style)
        context_messages = len(self._sanitize_history(history or [], max_turns=self.settings.openclaw_context_turns))
        system_prompt = self._compose_system_prompt(profile_context, memory_context, response_style=response_style)
        started = time.perf_counter()

        claude_result: ClaudeChatResult | None = None
        if self.anthropic_client and _is_claude_model(normalized_model):
            try:
                claude_messages = self._sanitize_history(history or [], max_turns=self.settings.openclaw_context_turns)
                if not claude_messages:
                    claude_messages = [{"role": "user", "content": prompt}]
                else:
                    claude_messages = [*claude_messages, {"role": "user", "content": prompt}]
                claude_result = self.anthropic_client.chat(
                    model=normalized_model,
                    system=system_prompt if system_prompt else "",
                    messages=claude_messages,
                    max_tokens=token_budget or 1024,
                    temperature=0.7,
                )
                return OpenClawResult(
                    ok=True,
                    text=claude_result.text,
                    raw={"provider": "anthropic"},
                    source="anthropic_direct",
                    latency_ms=claude_result.latency_ms,
                    cache_hit=False,
                    token_budget=token_budget,
                    context_messages=context_messages,
                    input_tokens=claude_result.input_tokens,
                    output_tokens=claude_result.output_tokens,
                    used_model=claude_result.model,
                    model_locked=False,
                    response_style=response_style,
                )
            except Exception as e:
                logger.warning("CLAUDE_FALLBACK error=%s falling_back_to=openai", str(e))
                model_name = (self.settings.ayex_fast_model or "gpt-4o-mini").strip()
                normalized_model = normalize_model_for_openai(model_name)

        try:
            # Deliberately bypass agent-level canned fallback text when OpenClaw is disabled.
            # In this mode we must return only real model output or an explicit failure.
            enriched = self._compose_direct_prompt(
                prompt=prompt,
                history=history or [],
                profile_context=profile_context,
                memory_context=memory_context,
            )
            # GPT-5 does not support temperature.
            response_temperature: float | None = 0.2
            if "gpt-5" in str(normalized_model or "").lower():
                response_temperature = None
            response = self.openai.call_responses(
                prompt=enriched,
                model=model_name,
                instructions=system_prompt,
                max_output_tokens=token_budget,
                route_name=route_name,
                temperature=response_temperature,
            )
            in_tokens, out_tokens = self._extract_usage_tokens(response.raw)
            return OpenClawResult(
                ok=True,
                text=response.text,
                raw={**response.raw, "_mode": "openai_direct", "_original_model": model_name, "_normalized_model": normalized_model},
                source="openai_direct",
                latency_ms=response.latency_ms,
                cache_hit=False,
                token_budget=token_budget,
                context_messages=context_messages,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                used_model=response.used_model,
                model_locked=False,
                response_style=response_style,
            )
        except Exception as exc:
            logger.error("OPENAI_DIRECT_FAILURE route=%s model=%s error=%s", route_name, model_name, exc)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return OpenClawResult(
                ok=False,
                text="Model yaniti alinamadi. Lutfen tekrar dene.",
                raw={
                    "error": str(exc),
                    "mode": "openai_direct",
                    "original_model": model_name,
                    "normalized_model": normalized_model,
                },
                source="openai_direct",
                latency_ms=latency_ms,
                cache_hit=False,
                token_budget=token_budget,
                context_messages=context_messages,
                used_model=normalized_model,
                model_locked=False,
                response_style=response_style,
            )

    def _compose_direct_prompt(
        self,
        prompt: str,
        history: list[dict[str, str]],
        profile_context: str | None,
        memory_context: str | None,
    ) -> str:
        blocks: list[str] = []
        clean_history = self._sanitize_history(history, max_turns=self.settings.openclaw_context_turns)
        if clean_history:
            hist = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in clean_history])
            blocks.append(f"Yakın konuşma bağlamı:\n{hist}")
        if profile_context:
            blocks.append(f"Profil bağlamı:\n{profile_context.strip()[:1400]}")
        if memory_context:
            blocks.append(f"Uzun dönem konuşma bağlamı:\n{memory_context.strip()[:1600]}")
        blocks.append(prompt)
        return "\n\n".join([b for b in blocks if b.strip()])

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
        return ""

    def _localize_fallback(self, text: str) -> str:
        t = text.strip()
        if t.lower() in {"no response from openclaw.", "no response from model.", "no response", "no reply from agent."}:
            return "Model yanit uretemedi."
        return t

    def _friendly_error(self, err: str) -> str:
        low = err.lower()
        if "401" in low:
            return "Kimlik doğrulama hatası (401). API anahtarını kontrol et."
        if "timed out" in low or "timeout" in low:
            return "Model yaniti alinamadi. Lutfen tekrar dene."
        if "connection refused" in low or "failed to establish" in low:
            return "Model yaniti alinamadi. Lutfen tekrar dene."
        return "Model yaniti alinamadi. Lutfen tekrar dene."

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

    def _compose_system_prompt(self, profile_context: str | None, memory_context: str | None, response_style: str = "normal") -> str:
        base = self.settings.openclaw_instructions.strip()
        parts = [base]
        style_hint = (response_style or "normal").strip().lower()
        if style_hint == "brief":
            parts.append("Yanit format stili: brief (2-4 cumle, kisa ve net).")
        elif style_hint == "deep":
            parts.append("Yanit format stili: deep (detayli analiz, gerektiginde maddeli).")
        else:
            parts.append("Yanit format stili: normal (1-2 paragraf, net ve aciklayici).")
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

    def _compute_token_budget(self, prompt: str, response_style: str = "normal") -> int:
        style = (response_style or "normal").strip().lower()
        if style == "brief":
            base = max(220, min(340, self.settings.openclaw_max_output_tokens))
        elif style == "deep":
            base = max(580, min(900, self.settings.openclaw_max_output_tokens + 320))
        else:
            base = max(320, min(640, self.settings.openclaw_max_output_tokens + 180))
        words = len(prompt.split())
        if words <= 6:
            return max(int(base * 0.85), min(int(base * 0.95), base))
        if words <= 14:
            return max(int(base * 0.9), min(int(base * 0.97), base))
        if words >= 40:
            return min(1200, max(base + 120, int(base * 1.12)))
        if words >= 24:
            return min(1000, max(base + 80, int(base * 1.08)))
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
                source=res.source,
                latency_ms=0,
                cache_hit=True,
                token_budget=res.token_budget,
                context_messages=res.context_messages,
                input_tokens=res.input_tokens,
                output_tokens=res.output_tokens,
                used_model=res.used_model,
                model_locked=res.model_locked,
                response_style=res.response_style,
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
        if self.settings.openclaw_force_model and self.is_enabled():
            return configured
        return (requested_model or configured).strip()

    def _extract_used_model(self, raw: dict, fallback: str) -> str:
        val = raw.get("model")
        if isinstance(val, str) and val.strip():
            return val.strip()
        return fallback

    def _extract_usage_tokens(self, raw: dict) -> tuple[int, int]:
        usage = raw.get("usage")
        if not isinstance(usage, dict):
            return 0, 0
        input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        return input_tokens, output_tokens


def _is_claude_model(model: str) -> bool:
    low = model.lower()
    return any(x in low for x in ("claude", "haiku", "sonnet", "opus"))
