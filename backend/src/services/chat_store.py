from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from backend.src.config.env import BackendSettings


@dataclass
class ChatSession:
    id: str
    title: str
    created_at: str
    updated_at: str
    last_preview: str
    turn_count: int


class ChatStore:
    def __init__(self, settings: BackendSettings):
        self.root = Path(settings.chat_dir)
        self.session_dir = self.root / "sessions"
        self.index_path = self.root / "sessions.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text("{}", encoding="utf-8")
        self._lock = threading.Lock()

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_index(self, index: Dict[str, Dict[str, Any]]) -> None:
        self.index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def _msg_path(self, session_id: str) -> Path:
        return self.session_dir / f"{session_id}.jsonl"

    def _session_title_from_text(self, text: str) -> str:
        words = [w for w in text.strip().split() if w]
        if not words:
            return "Yeni Sohbet"
        return " ".join(words[:6])[:56]

    def create_session(self, title: str | None = None) -> ChatSession:
        with self._lock:
            session_id = uuid4().hex[:12]
            now = self._now()
            meta = {
                "id": session_id,
                "title": (title or "Yeni Sohbet").strip()[:56] or "Yeni Sohbet",
                "created_at": now,
                "updated_at": now,
                "last_preview": "",
                "turn_count": 0,
            }
            index = self._load_index()
            index[session_id] = meta
            self._save_index(index)
            self._msg_path(session_id).touch(exist_ok=True)
            return ChatSession(**meta)

    def ensure_session(self, session_id: str | None = None, title_hint: str | None = None) -> ChatSession:
        with self._lock:
            index = self._load_index()
            if session_id and session_id in index:
                return ChatSession(**index[session_id])
        title = self._session_title_from_text(title_hint or "") if title_hint else "Yeni Sohbet"
        return self.create_session(title=title)

    def list_sessions(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self._lock:
            index = self._load_index()
            items = sorted(index.values(), key=lambda x: x.get("updated_at", ""), reverse=True)
            return items[: max(1, min(200, limit))]

    def get_session(self, session_id: str) -> Dict[str, Any] | None:
        with self._lock:
            return self._load_index().get(session_id)

    def _update_meta_after_message(self, session_id: str, role: str, text: str) -> Dict[str, Any] | None:
        index = self._load_index()
        meta = index.get(session_id)
        if not meta:
            return None
        if role == "user" and (meta.get("title") == "Yeni Sohbet"):
            meta["title"] = self._session_title_from_text(text)
        if role == "assistant":
            meta["turn_count"] = int(meta.get("turn_count", 0)) + 1
        meta["last_preview"] = text.strip()[:120]
        meta["updated_at"] = self._now()
        index[session_id] = meta
        self._save_index(index)
        return meta

    def append_message(
        self,
        session_id: str,
        role: str,
        text: str,
        source: str = "model_direct",
        latency_ms: int | None = None,
        metrics: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        msg = {
            "id": uuid4().hex[:12],
            "session_id": session_id,
            "ts": self._now(),
            "role": role,
            "text": text,
            "source": source,
            "latency_ms": latency_ms,
            "metrics": metrics or {},
        }
        with self._lock:
            path = self._msg_path(session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
            self._update_meta_after_message(session_id, role=role, text=text)
        return msg

    def messages(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            path = self._msg_path(session_id)
            if not path.exists():
                return []
            out: List[Dict[str, Any]] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out[-max(1, min(500, limit)) :]

    def update_message_metrics(self, session_id: str, message_id: str, metrics_patch: Dict[str, Any]) -> Dict[str, Any] | None:
        if not session_id or not message_id:
            return None
        with self._lock:
            path = self._msg_path(session_id)
            if not path.exists():
                return None
            messages: List[Dict[str, Any]] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            updated: Dict[str, Any] | None = None
            for row in messages:
                if str(row.get("id") or "").strip() != message_id:
                    continue
                metrics = dict(row.get("metrics") or {})
                metrics.update(dict(metrics_patch or {}))
                row["metrics"] = metrics
                updated = row
                break
            if updated is None:
                return None
            with path.open("w", encoding="utf-8") as f:
                for row in messages:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            return updated

    def model_context(self, session_id: str, turns: int = 6) -> List[Dict[str, str]]:
        msgs = self.messages(session_id, limit=max(2, turns * 2))
        context: List[Dict[str, str]] = []
        for m in msgs[-(turns * 2) :]:
            role = str(m.get("role") or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            text = str(m.get("text") or "").strip()
            if not text:
                continue
            context.append({"role": role, "content": text})
        return context

    def cross_session_recall(
        self,
        query: str,
        exclude_session_id: str | None = None,
        limit: int = 4,
        sessions_window: int = 20,
    ) -> List[Dict[str, Any]]:
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        sessions = self.list_sessions(limit=max(1, min(60, sessions_window)))
        candidates: List[Dict[str, Any]] = []
        for session in sessions:
            sid = str(session.get("id") or "")
            if not sid or sid == exclude_session_id:
                continue
            title = str(session.get("title") or "Sohbet")
            for msg in self.messages(sid, limit=60):
                role = str(msg.get("role") or "").strip().lower()
                if role not in {"user", "assistant"}:
                    continue
                text = str(msg.get("text") or "").strip()
                if not text:
                    continue
                score = self._memory_score(q_tokens, text)
                if score <= 0:
                    continue
                if "proje" in q_tokens and "proje" not in text.lower():
                    continue
                if role == "user":
                    score += 0.6
                candidates.append(
                    {
                        "score": score,
                        "session_id": sid,
                        "title": title,
                        "role": role,
                        "text": text[:300],
                        "ts": str(msg.get("ts") or ""),
                    }
                )

        candidates.sort(key=lambda x: (x["score"], x.get("ts", "")), reverse=True)
        picked: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in candidates:
            key = f"{item['session_id']}|{item['text'][:80]}"
            if key in seen:
                continue
            seen.add(key)
            picked.append(item)
            if len(picked) >= max(1, min(12, limit)):
                break
        return picked

    def recall_context_text(self, query: str, exclude_session_id: str | None = None, limit: int = 4) -> str:
        recalls = self.cross_session_recall(query=query, exclude_session_id=exclude_session_id, limit=limit)
        if not recalls:
            return ""
        lines: List[str] = []
        for idx, item in enumerate(recalls, start=1):
            lines.append(
                f"[{idx}] {item['title']} ({item['role']}): {item['text']}"
            )
        return "Gecmis sohbetlerden ilgili notlar:\\n" + "\\n".join(lines)

    def delete_session(self, session_id: str) -> bool:
        removed = False
        with self._lock:
            index = self._load_index()
            if session_id in index:
                index.pop(session_id)
                self._save_index(index)
                removed = True
            path = self._msg_path(session_id)
            if path.exists():
                path.unlink()
                removed = True
        return removed

    def recent_assistant_for_duplicate(self, session_id: str, user_text: str, max_age_sec: int = 45) -> Dict[str, Any] | None:
        recent = self.messages(session_id, limit=4)
        if len(recent) < 2:
            return None
        prev_user = recent[-2]
        prev_assistant = recent[-1]
        if prev_user.get("role") != "user" or prev_assistant.get("role") != "assistant":
            return None
        if str(prev_user.get("text", "")).strip().lower() != user_text.strip().lower():
            return None
        ts = str(prev_assistant.get("ts") or "")
        try:
            age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
        except ValueError:
            return None
        if age > max(0, max_age_sec):
            return None
        return prev_assistant

    def _tokenize(self, text: str) -> set[str]:
        words = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        return {w for w in words if len(w) >= 3}

    def _memory_score(self, q_tokens: set[str], text: str) -> float:
        t_tokens = self._tokenize(text)
        if not t_tokens:
            return 0.0
        overlap = len(q_tokens & t_tokens)
        if overlap == 0:
            return 0.0
        bonus = 0.0
        low = text.lower()
        if any(k in low for k in ("proje", "plan", "hedef", "mvp", "roadmap", "yol haritasi", "todo")):
            bonus += 1.2
        if len(text) >= 80:
            bonus += 0.2
        return float(overlap) + bonus
