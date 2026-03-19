from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


@dataclass
class IntelEvent:
    id: str = field(default_factory=lambda: uuid4().hex)
    title: str = ""
    summary: str = ""
    category: str = "general"
    importance: int = 5
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "internal"
    tags: list[str] = field(default_factory=list)
    importance_score: float = 0.0
    urgency_score: float = 0.0
    confidence_score: float = 0.0
    final_score: float = 0.0
