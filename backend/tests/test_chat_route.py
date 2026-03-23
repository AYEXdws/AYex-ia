from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

from backend.src.routes.chat import _format_all_events, chat
from backend.src.schemas import ChatRequest


class _FakeGuard:
    def __init__(self, ok: bool, reason: str = ""):
        self.ok = ok
        self.reason = reason
        self.usage = {}


class _FakeCostGuard:
    def __init__(self, ok: bool, reason: str = ""):
        self._ok = ok
        self._reason = reason

    def check_and_track(self, text: str):
        _ = text
        return _FakeGuard(ok=self._ok, reason=self._reason)


class _FakeSession:
    def __init__(self, session_id: str = "s1"):
        self.id = session_id


class _FakeChatStore:
    def __init__(self):
        self.appended: list[tuple[str, str, str]] = []

    def ensure_session(self, session_id, title_hint=None):
        _ = title_hint
        return _FakeSession(session_id or "s1")

    def recent_assistant_for_duplicate(self, session_id, user_text, max_age_sec):
        _ = (session_id, user_text, max_age_sec)
        return None

    def append_message(self, session_id, role, text, source="", latency_ms=None, metrics=None):
        _ = (latency_ms, metrics)
        self.appended.append((session_id, role, text))

    def model_context(self, session_id, turns):
        _ = (session_id, turns)
        return []

    def messages(self, session_id, limit=80):
        _ = (session_id, limit)
        return []


class _FakeIntelStore:
    def __init__(self, events):
        self._events = list(events)

    def get_all_events(self):
        return list(self._events)


class _FakeMemory:
    def get_memory_context(self, text):
        _ = text
        return ""

    def summarize_and_store(self, messages, session_id, openai_client):
        _ = (messages, session_id, openai_client)
        return None


class _FakeProfile:
    def prompt_context(self):
        return "PROFILE"

    def load(self):
        return {}


class _FakeLongMemory:
    def sync_profile(self, profile_data, user_id="ayex"):
        _ = (profile_data, user_id)

    def append_conversation(self, **kwargs):
        _ = kwargs


class _FakeModel:
    def __init__(self, text="Merhaba Ahmet, guncel verilere baktim."):
        self.openai = object()
        self._text = text
        self.calls = 0

    def run_action(self, *args, **kwargs):
        _ = (args, kwargs)
        self.calls += 1
        return SimpleNamespace(
            text=self._text,
            latency_ms=42,
            source="openai_direct",
            used_model="claude-haiku-4.5",
            response_style="normal",
            ok=True,
        )


class _FakeServices:
    def __init__(self, guard_ok=True, guard_reason="", model_text="Merhaba Ahmet, guncel verilere baktim."):
        self.cost_guard = _FakeCostGuard(ok=guard_ok, reason=guard_reason)
        self.chat_store = _FakeChatStore()
        self.settings = SimpleNamespace(model_cache_ttl_sec=45, model_context_turns=6)
        ev = SimpleNamespace(
            title="BTC 68k",
            summary="Fiyat 24 saatte dususte",
            category="economy",
            source="coingecko",
            timestamp=datetime.utcnow(),
            tags=["btc"],
        )
        self.intel = SimpleNamespace(store=_FakeIntelStore([ev]))
        self.memory = _FakeMemory()
        self.profile = _FakeProfile()
        self.model = _FakeModel(text=model_text)
        self.long_memory = _FakeLongMemory()


class _FakeRequest:
    def __init__(self):
        self.state = SimpleNamespace(user_id="ayex")


def test_chat_returns_guard_reason_when_blocked():
    services = _FakeServices(guard_ok=False, guard_reason="limit")
    payload = ChatRequest(text="merhaba")

    out = asyncio.run(chat(payload, _FakeRequest(), services=services))

    assert out.reply == "limit"
    assert out.metrics.get("source") == "guard"


def test_chat_success_persists_user_and_assistant_messages():
    services = _FakeServices()
    payload = ChatRequest(text="BTC ne durumda")

    out = asyncio.run(chat(payload, _FakeRequest(), services=services))

    assert out.reply
    assert out.metrics.get("used_model") == "claude-haiku-4.5"
    assert len(services.chat_store.appended) == 2
    assert services.chat_store.appended[0][1] == "user"
    assert services.chat_store.appended[1][1] == "assistant"
    assert services.model.calls == 1


def test_format_all_events_respects_prompt_budget():
    events = []
    for idx in range(25):
        events.append(
            SimpleNamespace(
                title=f"Event {idx}",
                summary="A" * 400,
                category="economy",
                source="n8n",
                timestamp=datetime.utcnow(),
                tags=["btc", "macro"],
            )
        )

    text = _format_all_events(events, max_events=25, max_chars=1200)

    assert len(text) <= 1200
    assert "prompt butcesi" in text or "EVENT" in text.upper()
