from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

from ayex_core import AyexAgent
from ayex_core.config import DEFAULT_MODEL


class AgentRegistry:
    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, str], AyexAgent] = {}

    def get_agent(self, workspace: Optional[str], model: Optional[str]) -> AyexAgent:
        ws = str(Path(workspace).resolve()) if workspace else str(Path.cwd().resolve())
        chosen_model = model or DEFAULT_MODEL
        cache_key = (ws, chosen_model)
        if cache_key not in self._cache:
            self._cache[cache_key] = AyexAgent(workspace=Path(ws), model=chosen_model)
        return self._cache[cache_key]
