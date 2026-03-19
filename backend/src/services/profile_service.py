from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from backend.src.config.env import BackendSettings


class ProfileService:
    def __init__(self, settings: BackendSettings):
        self.profile_path = Path(settings.profile_path)
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.profile_path.exists():
            self.profile_path.write_text(
                json.dumps(
                    {
                        "name": "Ahmet",
                        "assistant_name": "AYEX",
                        "communication_tone": "net, profesyonel, dogal",
                        "response_style": "kisa ve etkili",
                        "preferences": [],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

    def load(self) -> Dict[str, Any]:
        try:
            return json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {
                "name": "Ahmet",
                "assistant_name": "AYEX",
                "communication_tone": "net, profesyonel, dogal",
                "response_style": "kisa ve etkili",
                "preferences": [],
            }

    def update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        profile = self.load()
        profile.update(updates)
        self.profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        return profile

    def prompt_context(self) -> str:
        p = self.load()
        name = str(p.get("name") or "Ahmet").strip()
        aliases = p.get("aliases") or []
        calls = p.get("preferred_calls") or []
        tone = str(p.get("communication_tone") or p.get("tone") or "net ve profesyonel")
        style = str(p.get("response_style") or "kisa, dogal, odakli")
        goal = str(p.get("goal") or "")
        location = str(p.get("location") or "")
        prefs = p.get("preferences") or []
        focus_projects = p.get("focus_projects") or []

        aliases_text = ", ".join([str(x).strip() for x in aliases if str(x).strip()][:4]) or "yok"
        calls_text = ", ".join([str(x).strip() for x in calls if str(x).strip()][:4]) or name
        prefs_text = ", ".join([str(x).strip() for x in prefs if str(x).strip()][:5]) or "belirtilmedi"
        focus_text = ", ".join([str(x).strip() for x in focus_projects if str(x).strip()][:3]) or "AYEX"

        parts = [
            f"Kullanici profili: ad={name}, takma adlar={aliases_text}, tercih edilen hitap={calls_text}.",
            f"Iletisim tonu={tone}; cevap stili={style}.",
            f"Ilgi alanlari={prefs_text}; odak projeler={focus_text}.",
        ]
        if goal:
            parts.append(f"Ana hedef: {goal}.")
        if location:
            parts.append(f"Konum bilgisi: {location}.")
        return " ".join(parts)
