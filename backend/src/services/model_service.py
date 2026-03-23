from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from backend.src.config.env import BackendSettings, normalize_model_for_openai
from backend.src.services.anthropic_client import AnthropicClient, ClaudeChatResult
from backend.src.services.openai_client import OpenAIDirectClient
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ModelResult:
    ok: bool
    text: str
    raw: dict
    source: str = "openai_direct"
    latency_ms: int = 0
    cache_hit: bool = False
    token_budget: int = 0
    context_messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    used_model: str = ""
    model_locked: bool = False
    response_style: str = "normal"


class ModelService:
    """Direct model gateway (OpenAI + Anthropic) for AYEX backend."""

    def __init__(self, settings: BackendSettings, anthropic_client: AnthropicClient | None = None):
        self.settings = settings
        self.openai = OpenAIDirectClient(settings)
        self.anthropic_client = anthropic_client
        self._cache: dict[str, tuple[float, ModelResult]] = {}

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
    ) -> ModelResult:
        _ = workspace
        prompt = (text or "").strip()
        if not prompt:
            return ModelResult(ok=False, text="Bos mesaj gonderilemez.", raw={"error": "empty_prompt"})

        model_name = self._resolve_model(model)
        normalized_model = normalize_model_for_openai(model_name)
        context = self._sanitize_history(history or [], max_turns=self.settings.model_context_turns)
        context_messages = len(context)
        token_budget = self._compute_token_budget(prompt, response_style=response_style)
        system_prompt = self._compose_system_prompt(profile_context, memory_context, response_style=response_style)

        cache_key = self._cache_key(model=normalized_model, prompt=prompt, system_prompt=system_prompt, history=context)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        started = time.perf_counter()

        if self.anthropic_client and _is_claude_model(normalized_model):
            try:
                claude_messages = context or [{"role": "user", "content": prompt}]
                if claude_messages[-1]["role"] != "user":
                    claude_messages = [*claude_messages, {"role": "user", "content": prompt}]
                else:
                    claude_messages = [*claude_messages, {"role": "assistant", "content": "."}, {"role": "user", "content": prompt}]
                claude_result: ClaudeChatResult = self.anthropic_client.chat(
                    model=normalized_model,
                    system=system_prompt,
                    messages=claude_messages,
                    max_tokens=token_budget,
                    temperature=0.7,
                )
                result = ModelResult(
                    ok=True,
                    text=claude_result.text,
                    raw={"provider": "anthropic"},
                    source="anthropic_direct",
                    latency_ms=claude_result.latency_ms,
                    token_budget=token_budget,
                    context_messages=context_messages,
                    input_tokens=claude_result.input_tokens,
                    output_tokens=claude_result.output_tokens,
                    used_model=claude_result.model,
                    model_locked=False,
                    response_style=response_style,
                )
                self._cache_set(cache_key, result)
                return result
            except Exception as exc:
                logger.warning("CLAUDE_FALLBACK error=%s fallback=%s", exc, self.settings.ayex_fast_model)
                model_name = (self.settings.ayex_fast_model or "gpt-4o-mini").strip()
                normalized_model = normalize_model_for_openai(model_name)

        try:
            enriched = self._compose_direct_prompt(
                prompt=prompt,
                history=history or [],
                profile_context=profile_context,
                memory_context=memory_context,
            )
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
            result = ModelResult(
                ok=True,
                text=response.text,
                raw={**response.raw, "_mode": "direct", "_normalized_model": normalized_model},
                source="openai_direct",
                latency_ms=response.latency_ms,
                token_budget=token_budget,
                context_messages=context_messages,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                used_model=response.used_model,
                model_locked=False,
                response_style=response_style,
            )
            self._cache_set(cache_key, result)
            return result
        except Exception as exc:
            logger.error("MODEL_CALL_FAILED route=%s model=%s error=%s", route_name, model_name, exc)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return ModelResult(
                ok=False,
                text="Model yaniti alinamadi. Lutfen tekrar dene.",
                raw={"error": str(exc), "mode": "direct", "normalized_model": normalized_model},
                source="openai_direct",
                latency_ms=latency_ms,
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
        clean_history = self._sanitize_history(history, max_turns=self.settings.model_context_turns)
        if clean_history:
            hist = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in clean_history])
            blocks.append(f"Yakin konusma baglami:\n{hist}")
        if profile_context:
            blocks.append(f"Profil baglami:\n{profile_context.strip()[:1600]}")
        if memory_context:
            blocks.append(f"Uzun donem konusma baglami:\n{memory_context.strip()[:1600]}")
        blocks.append(prompt)
        return "\n\n".join([b for b in blocks if b.strip()])

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
            clean.append({"role": role, "content": content[:2200]})
        return clean

    def _compose_system_prompt(self, profile_context: str | None, memory_context: str | None, response_style: str = "normal") -> str:
        base = self.settings.model_instructions.strip()
        parts = [base]
        style_hint = (response_style or "normal").strip().lower()
        if style_hint == "brief":
            parts.append("Yanit stili: brief (2-4 cumle).")
        elif style_hint == "deep":
            parts.append("Yanit stili: deep (detayli analiz).")
        else:
            parts.append("Yanit stili: normal (net ve dogal).")

        profile = (profile_context or "").strip()
        memory = (memory_context or "").strip()
        if profile:
            parts.append(f"Profil baglami: {profile[:1500]}")
        if memory:
            parts.append(f"Uzun donem baglam: {memory[:1700]}")
        return "\n\n".join(parts)

    def _compute_token_budget(self, prompt: str, response_style: str = "normal") -> int:
        style = (response_style or "normal").strip().lower()
        if style == "brief":
            base = max(220, min(340, self.settings.model_max_output_tokens))
        elif style == "deep":
            base = max(580, min(900, self.settings.model_max_output_tokens + 320))
        else:
            base = max(320, min(640, self.settings.model_max_output_tokens + 180))

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

    def _cache_key(self, model: str, prompt: str, system_prompt: str, history: list[dict[str, str]]) -> str:
        history_blob = "\n".join([f"{m.get('role')}:{m.get('content')}" for m in history[-4:]])
        raw = f"{model}|{system_prompt}|{history_blob}|{prompt.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> ModelResult | None:
        if self.settings.model_cache_ttl_sec <= 0:
            return None
        item = self._cache.get(key)
        if not item:
            return None
        ts, result = item
        if (time.time() - ts) > self.settings.model_cache_ttl_sec:
            self._cache.pop(key, None)
            return None
        return ModelResult(
            ok=result.ok,
            text=result.text,
            raw=result.raw,
            source=result.source,
            latency_ms=0,
            cache_hit=True,
            token_budget=result.token_budget,
            context_messages=result.context_messages,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            used_model=result.used_model,
            model_locked=result.model_locked,
            response_style=result.response_style,
        )

    def _cache_set(self, key: str, result: ModelResult) -> None:
        if self.settings.model_cache_ttl_sec <= 0:
            return
        if len(self._cache) >= self.settings.model_cache_size:
            oldest = min(self._cache.items(), key=lambda x: x[1][0])[0]
            self._cache.pop(oldest, None)
        self._cache[key] = (time.time(), result)

    def _resolve_model(self, requested_model: str | None) -> str:
        default_model = (self.settings.ayex_chat_model or self.settings.ayex_model or "claude-haiku-4-5-20251001").strip()
        return (requested_model or default_model).strip()

    def _extract_usage_tokens(self, raw: dict) -> tuple[int, int]:
        usage = raw.get("usage")
        if not isinstance(usage, dict):
            return 0, 0
        input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        return input_tokens, output_tokens


def _is_claude_model(model: str) -> bool:
    low = str(model or "").lower()
    return any(x in low for x in ("claude", "haiku", "sonnet", "opus"))
