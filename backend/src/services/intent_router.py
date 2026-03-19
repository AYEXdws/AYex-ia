from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentResult:
    category: str
    confidence: float


class IntentRouter:
    """Intent detector for chat/search/market/url_read/agent_task."""

    def route(self, text: str) -> IntentResult:
        normalized = self._normalize(text)
        tokens = set(normalized.split())

        if self._has_url(normalized):
            return IntentResult(category="url_read", confidence=0.94)
        if self._is_agent_task(normalized):
            return IntentResult(category="agent_task", confidence=0.9)
        if self._is_market_request(normalized, tokens):
            return IntentResult(category="market", confidence=0.9)
        if self._is_search_request(normalized, tokens):
            return IntentResult(category="search", confidence=0.86)
        return IntentResult(category="chat", confidence=0.72)

    def _normalize(self, text: str) -> str:
        out = text.lower()
        repl = {
            "ı": "i",
            "ğ": "g",
            "ü": "u",
            "ş": "s",
            "ö": "o",
            "ç": "c",
        }
        for src, dst in repl.items():
            out = out.replace(src, dst)
        return " ".join(out.split())

    def _has_url(self, text: str) -> bool:
        return "http://" in text or "https://" in text or "www." in text

    def _is_search_request(self, text: str, tokens: set[str]) -> bool:
        triggers = {
            "arastir",
            "arasir",
            "ara",
            "internette",
            "webde",
            "googlela",
            "nedir",
            "kimdir",
        }
        return bool(tokens.intersection(triggers)) or "hakkinda bilgi" in text

    def _is_market_request(self, text: str, tokens: set[str]) -> bool:
        keys = {"piyasa", "btc", "bitcoin", "eth", "ethereum", "altin", "dolar", "kur", "kripto"}
        return bool(tokens.intersection(keys)) or "piyasa" in text

    def _is_agent_task(self, text: str) -> bool:
        return any(k in text for k in ("arastir", "analiz et", "karsilastir", "rapor hazirla", "plan cikar"))
