from __future__ import annotations

from typing import Any, Dict, List

from ayex_core.agent import AyexAgent


class MemoryManager:
    """Lightweight facade for future memory backends.

    For now this delegates to AyexAgent's file-based MemoryStore.
    """

    def profile(self, agent: AyexAgent) -> Dict[str, Any]:
        return agent.memory.load_profile()

    def recent_context(self, agent: AyexAgent, limit: int = 3) -> List[Dict[str, str]]:
        return list(agent.history)[-limit:]

    def last_topic(self, agent: AyexAgent) -> str:
        if not agent.history:
            return ""
        return str(agent.history[-1].get("user", "")).strip()
