from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from backend.src.routes.events import ingest_event


class _FakeRequest:
    def __init__(self, payload: dict, *, headers: dict | None = None, client_host: str = "127.0.0.1"):
        self._payload = payload
        self.state = SimpleNamespace(user_id="ayex")
        self.headers = dict(headers or {})
        self.client = SimpleNamespace(host=client_host)

    async def json(self) -> dict:
        return self._payload


@dataclass
class _CreatedEvent:
    id: str = "ev-1"
    title: str = "BTC"
    final_score: float = 0.8


class _FakeIntel:
    def validate_event_payload(self, merged: dict) -> dict:
        return {
            "title": str(merged.get("title") or "t"),
            "summary": str(merged.get("summary") or "s"),
            "category": str(merged.get("category") or "economy"),
            "importance": int(merged.get("importance") or 5),
            "source": str(merged.get("source") or "n8n"),
            "tags": list(merged.get("tags") or []),
            "timestamp": merged.get("timestamp") or datetime.utcnow(),
            "type": str(merged.get("type") or "intel"),
        }

    def create_event(self, **kwargs):
        _ = kwargs
        return _CreatedEvent()


class _FakeLongMemory:
    def __init__(self):
        self.calls = 0

    def append_event(self, **kwargs):
        _ = kwargs
        self.calls += 1


class _FakeServices:
    def __init__(self, *, ingest_token: str = "", ingest_rpm: int = 120):
        self.intel = _FakeIntel()
        self.long_memory = _FakeLongMemory()
        self.settings = SimpleNamespace(
            intel_ingest_token=ingest_token,
            intel_ingest_rate_per_minute=ingest_rpm,
        )


def test_events_ingest_accepts_payload_wrapper():
    payload = {
        "type": "intel",
        "source": "n8n",
        "payload": {
            "title": "BTC 70k",
            "summary": "fiyat yukselisi",
            "category": "economy",
            "importance": 8,
            "tags": ["btc"],
        },
    }
    req = _FakeRequest(payload)
    services = _FakeServices()

    out = asyncio.run(ingest_event(req, services=services))

    assert out["status"] == "ok"
    assert out["stored"] is True
    assert services.long_memory.calls == 1


def test_events_ingest_rejects_without_required_ingest_token():
    payload = {
        "type": "intel",
        "source": "n8n",
        "payload": {"title": "BTC 70k", "summary": "fiyat yukselisi", "category": "economy", "importance": 8},
    }
    req = _FakeRequest(payload)
    services = _FakeServices(ingest_token="secret-token")

    out = asyncio.run(ingest_event(req, services=services))

    assert out["status"] == "skipped"
    assert out["reason"] == "unauthorized"


def test_events_ingest_rate_limited_after_threshold():
    payload = {
        "type": "intel",
        "source": "n8n",
        "payload": {"title": "BTC 70k", "summary": "fiyat yukselisi", "category": "economy", "importance": 8},
    }
    services = _FakeServices(ingest_rpm=1)
    req1 = _FakeRequest(payload, client_host="10.0.0.2")
    req2 = _FakeRequest(payload, client_host="10.0.0.2")

    out1 = asyncio.run(ingest_event(req1, services=services))
    out2 = asyncio.run(ingest_event(req2, services=services))

    assert out1["status"] == "ok"
    assert out2["status"] == "skipped"
    assert out2["reason"] == "rate_limited"
