from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from backend.src.config.env import BackendSettings
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


class MemorySummarizer:
    """
    Summarizes conversations and stores them as memories.
    Storage: .ayex/memory_summaries.json
    """

    def __init__(self, settings: BackendSettings):
        self.path = Path(settings.data_dir).expanduser().resolve() / "memory_summaries.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")
        self._lock = threading.Lock()

    def summarize_and_store(self, messages: list, session_id: str, openai_client) -> dict:
        rows = list(messages or [])
        transcript = self._build_transcript(rows, max_messages=18)
        if not transcript.strip():
            return {}

        fingerprint = hashlib.sha256(f"{session_id}|{transcript}".encode("utf-8")).hexdigest()[:16]
        existing = self._load()
        if any(str(item.get("fingerprint") or "") == fingerprint for item in existing):
            return {}

        summary_text = self._summarize_with_model(transcript, openai_client=openai_client)
        if not summary_text:
            summary_text = self._fallback_summary(rows)

        keywords = self._extract_keywords(f"{summary_text}\n{transcript}", limit=6)
        topic = self._detect_topic(summary_text, keywords)
        now = datetime.utcnow()
        entry = {
            "id": uuid4().hex,
            "date": now.date().isoformat(),
            "timestamp": now.isoformat(),
            "summary": summary_text[:900],
            "keywords": keywords,
            "topic": topic,
            "session_id": str(session_id or ""),
            "fingerprint": fingerprint,
        }

        with self._lock:
            data = self._load()
            data.append(entry)
            data.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)
            self._save(data)
        return entry

    def search_memories(self, query: str, limit: int = 5) -> list:
        q_tokens = self._extract_keywords(query, limit=10)
        if not q_tokens:
            return []
        items = self._load()
        matched: list[dict] = []
        for item in items:
            keywords = [str(k).lower() for k in (item.get("keywords") or [])]
            summary = str(item.get("summary") or "").lower()
            score = 0.0
            for tok in q_tokens:
                if tok in keywords:
                    score += 2.0
                    continue
                if any(tok in kw or kw in tok for kw in keywords):
                    score += 1.4
                if tok in summary:
                    score += 1.0
            if score <= 0:
                continue
            row = dict(item)
            row["_score"] = round(score, 4)
            matched.append(row)
        matched.sort(key=lambda x: (str(x.get("timestamp") or ""), float(x.get("_score", 0.0))), reverse=True)
        return matched[: max(1, min(25, limit))]

    def get_recent_memories(self, days: int = 7, limit: int = 10) -> list:
        items = self._load()
        cutoff = datetime.utcnow() - timedelta(days=max(1, days))
        out: list[dict] = []
        for item in items:
            ts = self._parse_ts(str(item.get("timestamp") or ""))
            if ts is None:
                continue
            if ts >= cutoff:
                out.append(item)
        out.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)
        return out[: max(1, min(50, limit))]

    def get_memory_context(self, query: str) -> str:
        memories = self.search_memories(query, limit=5)
        if not memories:
            memories = self.get_recent_memories(days=7, limit=4)
        return self.format_for_prompt(memories)

    def format_for_prompt(self, memories: list) -> str:
        rows = list(memories or [])
        if not rows:
            return ""
        lines = ["GEÇMİŞ KONUŞMALAR:"]
        for item in rows[:8]:
            ts = self._parse_ts(str(item.get("timestamp") or ""))
            day = ts.strftime("%d %b") if ts is not None else str(item.get("date") or "")
            topic = str(item.get("topic") or "Genel")
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            lines.append(f"[{day}] {topic}: {summary[:220]}")
        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    def _summarize_with_model(self, transcript: str, openai_client) -> str:
        if openai_client is None:
            return ""
        prompt = (
            "Aşağıdaki konuşmayı Türkçe, en fazla 150 kelime ile özetle.\n"
            "Odak: kullanıcının amacı, aldığı kararlar, açık kalan sorular.\n\n"
            f"Konuşma:\n{transcript}\n\n"
            "Sadece düz metin özet döndür."
        )
        try:
            res = openai_client.call_responses(
                prompt=prompt,
                model="gpt-4o-mini",
                instructions="Kısa, net, Türkçe bir özet üret. 150 kelimeyi geçme.",
                max_output_tokens=220,
                route_name="memory_summarizer",
            )
            text = str(getattr(res, "text", "") or "").strip()
            return text[:900]
        except Exception as exc:
            logger.info("MEMORY_SUMMARY_MODEL_FAIL error=%s", exc)
            return ""

    def _fallback_summary(self, messages: list) -> str:
        user_msgs = [str(m.get("text") or "").strip() for m in messages if str(m.get("role") or "") == "user"]
        assistant_msgs = [str(m.get("text") or "").strip() for m in messages if str(m.get("role") or "") == "assistant"]
        user_last = user_msgs[-2:] if user_msgs else []
        assistant_last = assistant_msgs[-2:] if assistant_msgs else []
        joined = " | ".join([x for x in [*user_last, *assistant_last] if x])
        if not joined:
            return "Bugünkü konuşmada kullanıcı birden fazla konuda yönlendirme istedi."
        return f"Konuşma özeti: {joined[:820]}"

    def _build_transcript(self, messages: list, max_messages: int = 18) -> str:
        rows = list(messages or [])[-max(2, max_messages) :]
        lines: list[str] = []
        for item in rows:
            role = str(item.get("role") or "").strip().lower()
            text = str(item.get("text") or "").strip()
            if role not in {"user", "assistant"} or not text:
                continue
            prefix = "Kullanıcı" if role == "user" else "Asistan"
            lines.append(f"{prefix}: {text}")
        return "\n".join(lines)

    def _extract_keywords(self, text: str, limit: int = 6) -> list[str]:
        stop = {
            "ve",
            "ile",
            "ama",
            "gibi",
            "icin",
            "this",
            "that",
            "the",
            "from",
            "bir",
            "daha",
            "sonra",
            "kadar",
            "olan",
            "olarak",
            "neden",
            "nasil",
            "bugun",
            "dun",
        }
        tokens = re.findall(r"[a-zA-Z0-9_çğıöşüÇĞİÖŞÜ]{3,}", (text or "").lower())
        freq: dict[str, int] = {}
        for tok in tokens:
            t = tok.strip().lower()
            if not t or t in stop:
                continue
            freq[t] = freq.get(t, 0) + 1
        ordered = sorted(freq.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
        return [item[0] for item in ordered[: max(1, min(12, limit))]]

    def _detect_topic(self, summary: str, keywords: list[str]) -> str:
        blob = f"{summary} {' '.join(keywords)}".lower()
        if any(k in blob for k in ("btc", "kripto", "crypto", "piyasa", "market")):
            return "Kripto analizi"
        if any(k in blob for k in ("guvenlik", "security", "breach", "hack", "siber")):
            return "Siber güvenlik"
        if any(k in blob for k in ("ayex", "deploy", "sistem", "mimari", "backend", "frontend")):
            return "AYEX-IA projesi"
        if any(k in blob for k in ("yks", "okul", "sinav")):
            return "Kişisel plan"
        return "Genel"

    def _parse_ts(self, value: str) -> datetime | None:
        v = (value or "").strip()
        if not v:
            return None
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = []
        return data if isinstance(data, list) else []

    def _save(self, rows: list[dict]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
