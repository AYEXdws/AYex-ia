from __future__ import annotations

from types import SimpleNamespace

from backend.src.routes.health import health_ready


class _FakeIntelStore:
    def get_all_events(self):
        return [1, 2, 3]


class _FakeMemory:
    def retry_queue_size(self):
        return 2


class _FakeCostGuard:
    def usage_today(self):
        return {"requests": 11, "input_chars": 1000}


class _FakeServices:
    def __init__(self):
        self.settings = SimpleNamespace(
            ayex_chat_model="claude-haiku-4-5-20251001",
            ayex_reasoning_model="claude-sonnet-4-6",
            ayex_power_model="gpt-4.1",
            ayex_fast_model="gpt-4o",
        )
        self.intel = SimpleNamespace(store=_FakeIntelStore())
        self.memory = _FakeMemory()
        self.cost_guard = _FakeCostGuard()


def test_health_ready_reports_runtime(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")

    out = health_ready(services=_FakeServices())

    assert out["status"] == "ok"
    assert out["checks"]["openai_configured"] is True
    assert out["runtime"]["intel_event_count"] == 3
    assert out["runtime"]["memory_retry_queue"] == 2
