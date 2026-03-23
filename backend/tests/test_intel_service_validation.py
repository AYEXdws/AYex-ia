from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.src.intel.intel_service import IntelService
from backend.src.intel.intel_store import IntelStore


def _service() -> IntelService:
    return IntelService(IntelStore())


def test_validate_event_payload_normalizes_alias_category_and_timestamp():
    service = _service()
    ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "title": "Bitcoin ETF hareketlendi",
        "summary": "Piyasada hacim artisi goruldu ve volatilite yukselisi kaydedildi.",
        "category": "crypto",
        "importance": 8,
        "source": "n8n-feed",
        "timestamp": ts,
        "tags": ["btc", "etf"],
    }

    cleaned = service.validate_event_payload(payload)

    assert cleaned["category"] == "economy"
    assert isinstance(cleaned["timestamp"], datetime)
    assert cleaned["source"] == "n8n-feed"


def test_validate_event_payload_rejects_invalid_category():
    service = _service()
    payload = {
        "title": "Jeopolitik baslik",
        "summary": "Uzun ve gecerli bir aciklama metni burada yer aliyor.",
        "category": "sports",
        "importance": 5,
        "source": "n8n",
    }

    with pytest.raises(ValueError, match="category_invalid"):
        service.validate_event_payload(payload)


def test_validate_event_payload_rejects_future_timestamp():
    service = _service()
    future_ts = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    payload = {
        "title": "Fed aciklamasi beklentisi",
        "summary": "Gecerli uzunlukta bir ozet metni ile test verisi uretilmistir.",
        "category": "economy",
        "importance": 7,
        "source": "n8n",
        "timestamp": future_ts,
    }

    with pytest.raises(ValueError, match="timestamp_future"):
        service.validate_event_payload(payload)
