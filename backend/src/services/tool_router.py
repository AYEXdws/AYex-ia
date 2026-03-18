from __future__ import annotations

from datetime import datetime
from typing import Optional

from ayex_core.agent import AyexAgent

from backend.src.memory.manager import MemoryManager


class ToolRouter:
    """Low-cost command responses to avoid unnecessary LLM calls."""

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    def try_handle(self, text: str, agent: AyexAgent) -> Optional[str]:
        normalized = self._normalize(text)

        if any(k in normalized for k in ["saat kac", "simdi saat", "su an saat"]):
            now = datetime.now()
            return f"Ahmet, su an saat {now.strftime('%H:%M')}."

        if any(k in normalized for k in ["bugun gunlerden", "bugun ne gunu", "tarih ne"]):
            now = datetime.now()
            return f"Ahmet, bugun {now.strftime('%d.%m.%Y %A')}."

        if "profil" in normalized and any(k in normalized for k in ["goster", "durum", "ozet"]):
            profile = self.memory_manager.profile(agent)
            goal = profile.get("goal", "kayitli degil")
            prefs = ", ".join(profile.get("preferences", [])[:3]) or "kayitli degil"
            return f"Ahmet, profil ozetin: hedef={goal}, ilgi={prefs}."

        if any(k in normalized for k in ["son konu", "en son konu"]):
            last_topic = self.memory_manager.last_topic(agent)
            if last_topic:
                return f"Ahmet, son konu: {last_topic}"
            return "Ahmet, henuz kayitli bir son konu yok."

        if any(k in normalized for k in ["bildirim", "telefon", "arama", "mesaj gonder"]):
            return "Ahmet, bu cihaz eylemi yolu hazirlandi; telefon entegrasyonu sonraki fazda aktif edilecek."

        return None

    def _normalize(self, text: str) -> str:
        out = text.lower().strip()
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
