from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StyleDecision:
    style: str
    reason: str


class ResponseStyleService:
    """Detects response style from user input and profile preference."""

    def detect(self, text: str, profile_style: str | None = None) -> StyleDecision:
        normalized = self._normalize(text)
        if any(k in normalized for k in ("kisa anlat", "ozetle", "kisa gec", "kisa yaz")):
            return StyleDecision(style="brief", reason="keyword")
        if any(
            k in normalized
            for k in (
                "hangi coin",
                "hangi kripto",
                "hangi token",
                "hangi hisse",
                "almaliyim",
                "almam lazim",
                "en mantikli",
                "kisa vadede",
                "kisa vade",
            )
        ):
            return StyleDecision(style="brief", reason="decision_query")
        if any(k in normalized for k in ("detayli anlat", "derin analiz", "ayrintili", "adim adim detay")):
            return StyleDecision(style="deep", reason="keyword")

        profile_norm = self._normalize(profile_style or "")
        if any(k in profile_norm for k in ("brief", "kisa")):
            return StyleDecision(style="brief", reason="profile")
        if any(k in profile_norm for k in ("deep", "detay", "derin")):
            return StyleDecision(style="deep", reason="profile")
        return StyleDecision(style="normal", reason="default")

    def instruction_for(self, style: str) -> str:
        s = (style or "normal").strip().lower()
        if s == "brief":
            return "Yanitini 2-4 cumle araliginda, net ve islevsel tut."
        if s == "deep":
            return "Detayli bir analiz yaz. Gerektiginde basliklar ve maddeler kullan."
        return "Net ve anlasilir yaz. Gerekli detaylari 1-2 paragrafta ver."

    def _normalize(self, text: str) -> str:
        out = (text or "").strip().lower()
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
