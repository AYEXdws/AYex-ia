"""Systematic multi-model router for AYEX-IA.

Routing principles:
- chat: natural daily dialog and short interactions
- reasoning: dense synthesis, comparisons, multi-source interpretation
- power: strategy, investment, high-stakes decision support
- fast: acknowledgements and lightweight fallback path
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

REASONING_KEYWORDS = (
    "karşılaştır",
    "karsilastir",
    "compare",
    "analiz",
    "analyze",
    "detay",
    "derin",
    "difference",
    "neden",
    "sebep",
    "reason",
    "açıkla",
    "acikla",
    "explain",
    "trend",
    "tahmin",
    "forecast",
    "öngörü",
    "prediction",
    "fark",
    "korelasyon",
    "senaryo",
)

POWER_KEYWORDS = (
    "strateji",
    "strategy",
    "yatırım",
    "yatirim",
    "invest",
    "hangi hisseyi",
    "hangi coini",
    "which stock",
    "which coin",
    "portföy",
    "portfolio",
    "almalıyım",
    "almaliyim",
    "almali",
    "satmalıyım",
    "satmaliyim",
    "satmali",
    "en karlı",
    "en karli",
    "most profitable",
    "risk analizi",
    "risk analysis",
    "geopolitik",
    "geopolitical",
    "dünya ekonomisi",
    "dunya ekonomisi",
    "global economy",
    "para akışı",
    "para akisi",
    "money flow",
    "uzun vadeli",
    "long term",
    "kısa vadeli",
    "kisa vadeli",
    "short term",
)

MARKET_TERMS = (
    "btc",
    "eth",
    "sol",
    "xrp",
    "bnb",
    "bitcoin",
    "ethereum",
    "kripto",
    "coin",
    "hisse",
    "borsa",
    "dolar",
    "altın",
    "altin",
    "faiz",
    "enflasyon",
    "fiyat",
    "price",
    "market",
    "stock",
    "economy",
)

CASUAL_TERMS = (
    "merhaba",
    "selam",
    "naber",
    "nasılsın",
    "nasilsin",
    "tesekkur",
    "teşekkür",
    "eyvallah",
    "ok",
    "tamam",
)

FOLLOWUP_TERMS = (
    "devam",
    "az önce",
    "az once",
    "önceki",
    "onceki",
    "şimdi bunu",
    "simdi bunu",
    "peki",
)

ASSET_TERMS = (
    "btc",
    "eth",
    "sol",
    "xrp",
    "bnb",
    "bitcoin",
    "ethereum",
    "solana",
    "gold",
    "altın",
    "altin",
    "dolar",
    "usd",
    "euro",
    "eur",
    "aapl",
    "nvda",
    "tsla",
    "msft",
    "googl",
)


@dataclass
class ModelSelection:
    model: str
    provider: str
    reason: str
    route: str
    confidence: float = 0.5
    fallback_chain: tuple[str, ...] = field(default_factory=tuple)
    signals: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class RoutingFeatures:
    text_len: int
    token_count: int
    question_count: int
    numeric_count: int
    casual_hits: int
    reasoning_hits: int
    power_hits: int
    market_hits: int
    followup_hits: int
    asset_mentions: int
    compare_intent: bool
    timeframe_intent: bool
    action_intent: bool


def select_model(
    text: str,
    *,
    chat_model: str = "claude-haiku-4-5-20251001",
    reasoning_model: str = "claude-sonnet-4-6",
    power_model: str = "gpt-4.1",
    fast_model: str = "gpt-4o-mini",
    force_route: str | None = None,
    intel_event_count: int = 0,
    conversation_turn_count: int = 0,
    allow_anthropic: bool = True,
    allow_openai: bool = True,
) -> ModelSelection:
    """Select model using weighted, context-aware routing."""
    if force_route:
        return _forced_selection(
            force_route=force_route,
            chat_model=chat_model,
            reasoning_model=reasoning_model,
            power_model=power_model,
            fast_model=fast_model,
            allow_anthropic=allow_anthropic,
            allow_openai=allow_openai,
        )

    normalized = _normalize_text(text)
    f = _extract_features(normalized)
    scores = {"chat": 0.9, "reasoning": 0.55, "power": 0.35, "fast": 0.2}
    signals: list[str] = []

    if f.casual_hits > 0 and f.token_count <= 6:
        scores["fast"] += 2.2
        scores["chat"] += 1.0
        scores["reasoning"] -= 0.6
        scores["power"] -= 0.8
        signals.append("casual_short")

    if f.reasoning_hits > 0:
        boost = min(2.4, 0.55 * f.reasoning_hits)
        scores["reasoning"] += boost
        scores["power"] += boost * 0.25
        signals.append("reasoning_intent")

    if f.power_hits > 0:
        boost = min(3.6, 0.8 * f.power_hits)
        scores["power"] += boost
        scores["reasoning"] += boost * 0.35
        signals.append("power_intent")

    if f.compare_intent:
        scores["reasoning"] += 1.7
        scores["power"] += 0.5
        signals.append("compare_intent")

    if f.timeframe_intent:
        scores["reasoning"] += 0.9
        signals.append("timeframe_intent")

    if f.action_intent:
        scores["power"] += 1.2
        scores["reasoning"] += 0.4
        signals.append("action_intent")

    if f.asset_mentions >= 2:
        scores["reasoning"] += 1.1
        scores["power"] += 0.6
        signals.append("multi_asset")

    if f.market_hits > 0:
        scores["reasoning"] += min(1.0, 0.2 * f.market_hits)
        signals.append("market_context")

    if f.question_count >= 2:
        scores["reasoning"] += 0.7
        scores["power"] += 0.3
        signals.append("multi_question")

    if f.numeric_count >= 3:
        scores["reasoning"] += 0.5
        signals.append("numeric_dense")

    if f.token_count > 70:
        scores["reasoning"] += 1.1
        scores["power"] += 0.6
        signals.append("long_query")
    elif f.token_count > 35:
        scores["reasoning"] += 0.6
        signals.append("mid_long_query")

    if intel_event_count >= 6:
        scores["reasoning"] += 0.9
        signals.append("intel_dense")
    elif intel_event_count >= 3:
        scores["chat"] += 0.2
        scores["reasoning"] += 0.3
        signals.append("intel_available")

    if conversation_turn_count >= 8 and f.followup_hits > 0:
        scores["reasoning"] += 0.5
        signals.append("long_session_followup")

    route = max(scores, key=scores.get)
    confidence = _confidence_from_scores(scores)
    reason = _reason_from_signals(signals, route)
    preferred = _route_to_model(
        route=route,
        chat_model=chat_model,
        reasoning_model=reasoning_model,
        power_model=power_model,
        fast_model=fast_model,
    )
    fallback_chain = _build_fallback_chain(
        route=route,
        chat_model=chat_model,
        reasoning_model=reasoning_model,
        power_model=power_model,
        fast_model=fast_model,
        allow_anthropic=allow_anthropic,
        allow_openai=allow_openai,
    )
    selected_model = _first_available_model(
        [preferred, *fallback_chain],
        allow_anthropic=allow_anthropic,
        allow_openai=allow_openai,
    ) or preferred

    if selected_model != preferred:
        reason = f"{reason}|provider_failover"

    provider = _provider(selected_model)
    logger.info(
        "MODEL_ROUTE route=%s model=%s provider=%s confidence=%.2f reason=%s scores=%s signals=%s",
        route,
        selected_model,
        provider,
        confidence,
        reason,
        {k: round(v, 3) for k, v in scores.items()},
        ",".join(signals) if signals else "none",
    )
    return ModelSelection(
        model=selected_model,
        provider=provider,
        reason=reason,
        route=route,
        confidence=confidence,
        fallback_chain=tuple(_dedupe([selected_model, *fallback_chain])),
        signals=tuple(signals),
    )


def select_fast_model(fast_model: str = "gpt-4o-mini") -> ModelSelection:
    """Select fast model for background tasks (memory, tools)."""
    return ModelSelection(
        model=fast_model,
        provider=_provider(fast_model),
        reason="background_task",
        route="fast",
        confidence=0.95,
        fallback_chain=(fast_model,),
        signals=("background_task",),
    )


def _forced_selection(
    *,
    force_route: str,
    chat_model: str,
    reasoning_model: str,
    power_model: str,
    fast_model: str,
    allow_anthropic: bool,
    allow_openai: bool,
) -> ModelSelection:
    route_map = {
        "chat": chat_model,
        "reasoning": reasoning_model,
        "power": power_model,
        "fast": fast_model,
    }
    route = force_route if force_route in route_map else "chat"
    preferred = route_map[route]
    fallback_chain = _build_fallback_chain(
        route=route,
        chat_model=chat_model,
        reasoning_model=reasoning_model,
        power_model=power_model,
        fast_model=fast_model,
        allow_anthropic=allow_anthropic,
        allow_openai=allow_openai,
    )
    selected_model = _first_available_model(
        [preferred, *fallback_chain],
        allow_anthropic=allow_anthropic,
        allow_openai=allow_openai,
    ) or preferred
    reason = f"forced_{route}" if selected_model == preferred else f"forced_{route}|provider_failover"
    return ModelSelection(
        model=selected_model,
        provider=_provider(selected_model),
        reason=reason,
        route=route,
        confidence=0.99,
        fallback_chain=tuple(_dedupe([selected_model, *fallback_chain])),
        signals=(f"forced_{route}",),
    )


def _route_to_model(
    *,
    route: str,
    chat_model: str,
    reasoning_model: str,
    power_model: str,
    fast_model: str,
) -> str:
    if route == "power":
        return power_model
    if route == "reasoning":
        return reasoning_model
    if route == "fast":
        return fast_model
    return chat_model


def _build_fallback_chain(
    *,
    route: str,
    chat_model: str,
    reasoning_model: str,
    power_model: str,
    fast_model: str,
    allow_anthropic: bool,
    allow_openai: bool,
) -> list[str]:
    route_order: dict[str, list[str]] = {
        "chat": [chat_model, reasoning_model, fast_model, power_model],
        "reasoning": [reasoning_model, chat_model, power_model, fast_model],
        "power": [power_model, reasoning_model, chat_model, fast_model],
        "fast": [fast_model, chat_model, reasoning_model, power_model],
    }
    ordered = route_order.get(route, route_order["chat"])
    out: list[str] = []
    for model in ordered:
        if not model:
            continue
        if _is_available_model(model, allow_anthropic=allow_anthropic, allow_openai=allow_openai):
            out.append(model)
    return _dedupe(out)


def _first_available_model(
    candidates: list[str],
    *,
    allow_anthropic: bool,
    allow_openai: bool,
) -> str:
    for model in candidates:
        if _is_available_model(model, allow_anthropic=allow_anthropic, allow_openai=allow_openai):
            return model
    return ""


def _is_available_model(model: str, *, allow_anthropic: bool, allow_openai: bool) -> bool:
    provider = _provider(model)
    if provider == "anthropic":
        return allow_anthropic
    return allow_openai


def _extract_features(text: str) -> RoutingFeatures:
    tokens = [t for t in text.split() if t]
    question_count = text.count("?")
    numeric_count = len(re.findall(r"\d", text))
    casual_hits = _count_hits(text, CASUAL_TERMS)
    reasoning_hits = _count_hits(text, REASONING_KEYWORDS)
    power_hits = _count_hits(text, POWER_KEYWORDS)
    market_hits = _count_hits(text, MARKET_TERMS)
    followup_hits = _count_hits(text, FOLLOWUP_TERMS)
    asset_mentions = _count_hits(text, ASSET_TERMS)
    compare_intent = any(k in text for k in ("karşılaştır", "karsilastir", "compare", "fark", "vs", "veya"))
    timeframe_intent = any(k in text for k in ("dün", "dunku", "bugün", "bugun", "geçen hafta", "gecen hafta", "24 saat"))
    action_intent = any(
        k in text
        for k in (
            "ne yap",
            "ne yapmal",
            "öner",
            "oner",
            "almal",
            "satmal",
            "should i",
            "what should",
            "plan yap",
            "strateji",
        )
    )
    return RoutingFeatures(
        text_len=len(text),
        token_count=len(tokens),
        question_count=question_count,
        numeric_count=numeric_count,
        casual_hits=casual_hits,
        reasoning_hits=reasoning_hits,
        power_hits=power_hits,
        market_hits=market_hits,
        followup_hits=followup_hits,
        asset_mentions=asset_mentions,
        compare_intent=compare_intent,
        timeframe_intent=timeframe_intent,
        action_intent=action_intent,
    )


def _count_hits(text: str, words: tuple[str, ...]) -> int:
    return sum(1 for w in words if w in text)


def _normalize_text(text: str) -> str:
    low = (text or "").lower().strip()
    repl = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
    }
    for src, dst in repl.items():
        low = low.replace(src, dst)
    low = re.sub(r"\s+", " ", low)
    return low


def _confidence_from_scores(scores: dict[str, float]) -> float:
    ordered = sorted(scores.values(), reverse=True)
    if not ordered:
        return 0.5
    top = ordered[0]
    second = ordered[1] if len(ordered) > 1 else 0.0
    margin = top - second
    confidence = 0.52 + (margin / 4.0)
    if confidence < 0.35:
        return 0.35
    if confidence > 0.97:
        return 0.97
    return round(confidence, 3)


def _reason_from_signals(signals: list[str], route: str) -> str:
    if signals:
        return f"{route}:" + ",".join(signals[:4])
    return f"{route}:default"


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _provider(model: str) -> str:
    """Determine provider from model name."""
    low = str(model or "").lower()
    if any(k in low for k in ("claude", "haiku", "sonnet", "opus")):
        return "anthropic"
    return "openai"
