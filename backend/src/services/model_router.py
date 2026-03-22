"""Multi-model router for AYEX-IA.

Routes requests to the optimal model based on query type:
- Claude Haiku 4.5: default chat + intel analysis
- Claude Sonnet 4.6: deep analysis, comparisons
- GPT-5: ultra reasoning, strategy, investment
- GPT-4o-mini: memory summarization, tools, fallback
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

REASONING_KEYWORDS = (
    "karşılaştır",
    "karsilastir",
    "compare",
    "analiz et",
    "analyze",
    "detaylı",
    "detayli",
    "detailed",
    "derinlemesine",
    "deep",
    "fark ne",
    "farkı ne",
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
    "almali",
    "en karlı",
    "en karli",
    "most profitable",
    "risk analizi",
    "risk analysis",
    "sektör karşılaştır",
    "sektor karsilastir",
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
    "short term",
)


@dataclass
class ModelSelection:
    model: str
    provider: str
    reason: str
    route: str


def select_model(
    text: str,
    *,
    chat_model: str = "claude-haiku-4.5",
    reasoning_model: str = "claude-sonnet-4.6",
    power_model: str = "gpt-5",
    fast_model: str = "gpt-4o-mini",
    force_route: str | None = None,
    intel_event_count: int = 0,
) -> ModelSelection:
    """Select the best model for the given query.

    Args:
        text: user message
        chat_model: default chat model (Claude Haiku)
        reasoning_model: deep analysis model (Claude Sonnet)
        power_model: ultra reasoning model (GPT-5)
        fast_model: fast/cheap model (GPT-4o-mini)
        force_route: override route ("chat", "reasoning", "power", "fast")
        intel_event_count: number of intel events in context

    Returns:
        ModelSelection with model name, provider, reason, and route
    """
    if force_route:
        route_map = {
            "chat": (chat_model, _provider(chat_model), "forced_chat"),
            "reasoning": (reasoning_model, _provider(reasoning_model), "forced_reasoning"),
            "power": (power_model, _provider(power_model), "forced_power"),
            "fast": (fast_model, _provider(fast_model), "forced_fast"),
        }
        if force_route in route_map:
            m, p, r = route_map[force_route]
            return ModelSelection(model=m, provider=p, reason=r, route=force_route)

    low = text.lower().strip()

    if any(kw in low for kw in POWER_KEYWORDS):
        logger.info("MODEL_ROUTE route=power trigger=keyword model=%s", power_model)
        return ModelSelection(
            model=power_model,
            provider=_provider(power_model),
            reason="power_keyword_match",
            route="power",
        )

    if any(kw in low for kw in REASONING_KEYWORDS):
        logger.info("MODEL_ROUTE route=reasoning trigger=keyword model=%s", reasoning_model)
        return ModelSelection(
            model=reasoning_model,
            provider=_provider(reasoning_model),
            reason="reasoning_keyword_match",
            route="reasoning",
        )

    if intel_event_count > 3:
        logger.info("MODEL_ROUTE route=reasoning trigger=high_intel_count=%d model=%s", intel_event_count, reasoning_model)
        return ModelSelection(
            model=reasoning_model,
            provider=_provider(reasoning_model),
            reason=f"high_intel_count={intel_event_count}",
            route="reasoning",
        )

    logger.info("MODEL_ROUTE route=chat trigger=default model=%s", chat_model)
    return ModelSelection(
        model=chat_model,
        provider=_provider(chat_model),
        reason="default_chat",
        route="chat",
    )


def select_fast_model(fast_model: str = "gpt-4o-mini") -> ModelSelection:
    """Select fast model for background tasks (memory, tools)."""
    return ModelSelection(
        model=fast_model,
        provider=_provider(fast_model),
        reason="background_task",
        route="fast",
    )


def _provider(model: str) -> str:
    """Determine provider from model name."""
    if "claude" in model.lower() or "haiku" in model.lower() or "sonnet" in model.lower() or "opus" in model.lower():
        return "anthropic"
    return "openai"
