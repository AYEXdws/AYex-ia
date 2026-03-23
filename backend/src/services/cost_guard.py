from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from backend.src.config.env import BackendSettings

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None  # type: ignore


@dataclass
class GuardResult:
    ok: bool
    reason: str = ""
    usage: dict | None = None


class CostGuardService:
    def __init__(self, settings: BackendSettings):
        self.file = Path(settings.data_dir) / "usage-daily.json"
        self.lock_file = Path(settings.data_dir) / "usage-daily.lock"
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.req_limit = settings.daily_request_limit
        self.char_limit = settings.daily_input_char_limit
        self._lock = threading.Lock()
        if not self.file.exists():
            self.file.write_text("{}", encoding="utf-8")
        if not self.lock_file.exists():
            self.lock_file.write_text("", encoding="utf-8")

    def _today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _load(self) -> dict:
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict) -> None:
        tmp = self.file.with_suffix(self.file.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.file)

    @contextmanager
    def _guard_lock(self):
        with self._lock:
            handle = None
            try:
                if fcntl is not None:
                    handle = self.lock_file.open("a+", encoding="utf-8")
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                if handle is not None and fcntl is not None:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
                    handle.close()

    def check_and_track(self, input_text: str) -> GuardResult:
        with self._guard_lock():
            data = self._load()
            day = self._today()
            rec = data.get(day, {"requests": 0, "input_chars": 0})

            next_requests = int(rec.get("requests", 0)) + 1
            next_chars = int(rec.get("input_chars", 0)) + len(input_text or "")

            if next_requests > self.req_limit:
                return GuardResult(
                    ok=False,
                    reason=f"Gunluk istek limiti doldu ({self.req_limit}).",
                    usage={"requests": rec.get("requests", 0), "input_chars": rec.get("input_chars", 0)},
                )

            if next_chars > self.char_limit:
                return GuardResult(
                    ok=False,
                    reason=f"Gunluk giris karakter limiti doldu ({self.char_limit}).",
                    usage={"requests": rec.get("requests", 0), "input_chars": rec.get("input_chars", 0)},
                )

            rec["requests"] = next_requests
            rec["input_chars"] = next_chars
            data[day] = rec
            self._save(data)
            return GuardResult(ok=True, usage={"requests": next_requests, "input_chars": next_chars})

    def usage_today(self) -> dict:
        with self._guard_lock():
            data = self._load()
            day = self._today()
            rec = data.get(day, {"requests": 0, "input_chars": 0})
            rec["request_limit"] = self.req_limit
            rec["input_char_limit"] = self.char_limit
            return rec
