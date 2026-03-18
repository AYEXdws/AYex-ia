from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentResult:
    category: str
    confidence: float


class IntentRouter:
    """First-pass deterministic intent routing for low-latency path decisions."""

    def route(self, text: str) -> IntentResult:
        normalized = self._normalize(text)
        tokens = set(normalized.split())

        if self._is_simple_command(normalized, tokens):
            return IntentResult(category="simple_command", confidence=0.9)
        if self._is_memory_request(normalized, tokens):
            return IntentResult(category="memory_request", confidence=0.8)
        if self._is_device_action(normalized, tokens):
            return IntentResult(category="future_device_action", confidence=0.75)
        if text.strip().endswith("?") or tokens.intersection({"ne", "neden", "nasil", "kim", "hangi", "kac"}):
            return IntentResult(category="question", confidence=0.7)
        return IntentResult(category="conversation", confidence=0.6)

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

    def _is_simple_command(self, text: str, tokens: set[str]) -> bool:
        if any(k in text for k in ["saat kac", "tarih", "bugun gunlerden", "bugun ne gunu"]):
            return True
        quick_words = {"selam", "merhaba", "nasilsin", "kimsin", "adin", "ismin"}
        return len(tokens) <= 4 and bool(tokens.intersection(quick_words))

    def _is_memory_request(self, text: str, tokens: set[str]) -> bool:
        keys = {"hatirla", "hafiza", "bellek", "profil", "tercih", "son konu", "en son konu"}
        return any(k in text for k in keys) or bool(tokens.intersection({"profil", "bellek", "hafiza"}))

    def _is_device_action(self, text: str, tokens: set[str]) -> bool:
        keys = {
            "telefon",
            "bildirim",
            "arama",
            "mesaj",
            "wifi",
            "bluetooth",
            "kamera",
            "sensor",
            "alarm",
        }
        return bool(tokens.intersection(keys))
