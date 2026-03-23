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


def test_validate_event_payload_reclassifies_world_news_to_global_and_derives_tags():
    service = _service()
    payload = {
        "title": "Iranian missiles injure 180 in towns near Israeli nuclear site",
        "summary": "Israel is investigating how ballistic missiles got through the country's sophisticated air defences.",
        "category": "tech",
        "importance": 8,
        "source": "bbc_world",
        "tags": ["dunya", "haber", "gundem"],
    }

    cleaned = service.validate_event_payload(payload)

    assert cleaned["category"] == "global"
    assert "missile" in cleaned["tags"]
    assert "israel" in cleaned["tags"]


def test_validate_event_payload_rejects_low_signal_world_news():
    service = _service()
    payload = {
        "title": "OnlyFans owner Leonid Radvinsky dies at 43",
        "summary": "Leo Radvinsky became a billionaire after investing in the site, known for its pornographic content.",
        "category": "tech",
        "importance": 6,
        "source": "bbc_world",
        "tags": ["dunya", "haber", "gundem"],
    }

    with pytest.raises(ValueError, match="low_signal_event"):
        service.validate_event_payload(payload)


def test_validate_event_payload_does_not_misclassify_claims_as_ai():
    service = _service()
    payload = {
        "title": "Kenyan ex-foreign minister arrested and accused of staging his disappearance",
        "summary": "The reported disappearance of Raphael Tuju had led to claims he may have been abducted.",
        "category": "tech",
        "importance": 6,
        "source": "bbc_world",
        "tags": ["dunya", "haber", "gundem"],
    }

    cleaned = service.validate_event_payload(payload)

    assert cleaned["category"] == "global"
    assert "ai" not in cleaned["tags"]
