from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.src.config.env import BackendSettings


@dataclass(frozen=True)
class MemoryContext:
    profile: dict[str, Any]
    conversation_hits: list[dict[str, Any]]
    event_hits: list[dict[str, Any]]

    def as_text(self) -> str:
        parts: list[str] = []
        if self.profile:
            parts.append(f"Profil memory: {self.profile}")
        if self.conversation_hits:
            parts.append(f"Conversation memory: {self.conversation_hits}")
        if self.event_hits:
            parts.append(f"Event memory: {self.event_hits}")
        return "\n".join(parts).strip()


class LongMemoryService:
    def __init__(self, settings: BackendSettings):
        self.root = Path(settings.data_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def _paths(self, user_id: str) -> tuple[Path, Path, Path]:
        safe_user = re.sub(r"[^a-zA-Z0-9_-]+", "_", (user_id or "default")).strip("_") or "default"
        profile_path = self.root / f"memory_{safe_user}.json"
        conv_path = self.root / f"memory_conversations_{safe_user}.jsonl"
        events_path = self.root / f"memory_events_{safe_user}.jsonl"
        if not profile_path.exists():
            profile_path.write_text("{}", encoding="utf-8")
        if not conv_path.exists():
            conv_path.touch()
        if not events_path.exists():
            events_path.touch()
        return profile_path, conv_path, events_path

    def sync_profile(self, profile: dict[str, Any], user_id: str = "default") -> None:
        profile_path, _, _ = self._paths(user_id)
        merged = self._read_json(profile_path)
        merged.update(profile or {})
        profile_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_conversation(
        self,
        *,
        session_id: str,
        user_text: str,
        assistant_text: str,
        intent: str,
        style: str,
        user_id: str = "default",
    ) -> None:
        _, conv_path, _ = self._paths(user_id)
        row = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "style": style,
            "user": user_text[:1200],
            "assistant": assistant_text[:1600],
        }
        self._append_jsonl(conv_path, row)

    def append_event(self, *, event_type: str, payload: dict[str, Any], source: str, user_id: str = "default") -> None:
        _, _, events_path = self._paths(user_id)
        row = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "user_id": user_id,
            "type": event_type,
            "source": source,
            "payload": payload,
        }
        self._append_jsonl(events_path, row)

    def build_context(self, *, query: str, limit: int = 4, user_id: str = "default") -> MemoryContext:
        profile_path, conv_path, events_path = self._paths(user_id)
        profile = self._read_json(profile_path)
        q_tokens = self._tokenize(query)
        conv_hits = self._recall_jsonl(conv_path, q_tokens, limit=limit)
        event_hits = self._recall_jsonl(events_path, q_tokens, limit=limit)
        return MemoryContext(profile=profile, conversation_hits=conv_hits, event_hits=event_hits)

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _recall_jsonl(self, path: Path, q_tokens: set[str], limit: int) -> list[dict[str, Any]]:
        if not q_tokens:
            return []
        rows: list[dict[str, Any]] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            score = self._score_row(row, q_tokens)
            if score <= 0:
                continue
            row["_score"] = score
            rows.append(row)
            if len(rows) >= max(1, min(20, limit * 3)):
                break
        rows.sort(key=lambda x: float(x.get("_score", 0.0)), reverse=True)
        return rows[: max(1, min(10, limit))]

    def _score_row(self, row: dict[str, Any], q_tokens: set[str]) -> float:
        blob = json.dumps(row, ensure_ascii=False).lower()
        t = self._tokenize(blob)
        if not t:
            return 0.0
        return float(len(q_tokens & t))

    def _tokenize(self, text: str) -> set[str]:
        return {x for x in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if len(x) >= 3}
