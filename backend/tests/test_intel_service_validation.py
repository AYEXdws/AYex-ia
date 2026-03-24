from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.src.intel.intel_service import IntelService, select_relevant_intel_context
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


def test_validate_event_payload_rejects_low_importance_human_interest_world_news_without_strategic_signal():
    service = _service()
    payload = {
        "title": "Local TV star draws huge crowds after comeback show",
        "summary": "Fans gather in city center as entertainment buzz grows after the celebrity return.",
        "category": "global",
        "importance": 6,
        "source": "reuters",
        "tags": ["world"],
    }

    with pytest.raises(ValueError, match="low_signal_event"):
        service.validate_event_payload(payload)


def test_validate_event_payload_does_not_misclassify_claims_as_ai():
    service = _service()
    payload = {
        "title": "Kenyan election claims trigger parliament vote on coalition future",
        "summary": "Election claims escalated into a formal parliament vote over the ruling coalition's survival.",
        "category": "tech",
        "importance": 8,
        "source": "bbc_world",
        "tags": ["dunya", "haber", "gundem"],
    }

    cleaned = service.validate_event_payload(payload)

    assert cleaned["category"] == "global"
    assert "ai" not in cleaned["tags"]


def test_validate_event_payload_rejects_low_signal_missing_person_world_news():
    service = _service()
    payload = {
        "title": "Minister resurfaces after abduction fears in local political drama",
        "summary": "Missing person claims triggered media attention before the politician resurfaced safely.",
        "category": "global",
        "importance": 7,
        "source": "bbc_world",
        "tags": ["world"],
    }

    with pytest.raises(ValueError, match="low_signal_event"):
        service.validate_event_payload(payload)


def test_validate_event_payload_rejects_human_interest_war_profile_story():
    service = _service()
    payload = {
        "title": "A committed pharmacist and a homesick blogger – the Iranian civilians killed in the war",
        "summary": "A profile-style story about civilians killed in the war, focused on their personal lives rather than a strategic development.",
        "category": "global",
        "importance": 8,
        "source": "bbc_world",
        "tags": ["world"],
    }

    with pytest.raises(ValueError, match="low_signal_event"):
        service.validate_event_payload(payload)


def test_validate_event_payload_rejects_soft_conflict_story_without_hard_strategic_signal():
    service = _service()
    payload = {
        "title": "The alarming civilian cost of war in Iran grows as families flee",
        "summary": "A human-focused report about civilian toll and family displacement, without a new military, sanctions or energy development.",
        "category": "global",
        "importance": 8,
        "source": "bbc_world",
        "tags": ["world"],
    }

    with pytest.raises(ValueError, match="low_signal_event"):
        service.validate_event_payload(payload)


def test_validate_event_payload_rejects_soft_political_profile_story_without_major_signal():
    service = _service()
    payload = {
        "title": "President meets grieving families as civilian toll rises after overnight clashes",
        "summary": "A profile-led report focused on family accounts and civilian cost, without any strategic military, sanctions, trade or energy development.",
        "category": "global",
        "importance": 8,
        "source": "bbc_world",
        "tags": ["world"],
    }

    with pytest.raises(ValueError, match="low_signal_event"):
        service.validate_event_payload(payload)


def test_validate_event_payload_rejects_soft_political_world_story_without_power_shift_signal():
    service = _service()
    payload = {
        "title": "President meets grieving families as tensions persist after border attack",
        "summary": "A profile-led report centered on grieving families and political optics, without an election, coalition collapse, sanctions, trade or energy shock.",
        "category": "global",
        "importance": 8,
        "source": "bbc_world",
        "tags": ["world"],
    }

    with pytest.raises(ValueError, match="low_signal_event"):
        service.validate_event_payload(payload)


def test_select_relevant_intel_context_prefers_macro_source_over_profile_crypto_bias():
    service = IntelService(
        IntelStore(),
        profile_loader=lambda: {
            "preferred_categories": ["economy"],
            "interests": ["kripto", "btc", "bitcoin"],
            "topics": ["kripto", "bitcoin"],
        },
    )
    now = datetime.now(timezone.utc)
    service.create_event(
        title="Kripto Piyasasi: BTC $71.55K | +4.05% (24s)",
        summary="BTC ve SOL guclu gorunuyor.",
        category="economy",
        importance=8,
        source="coingecko",
        timestamp=now - timedelta(minutes=5),
        tags=["kripto", "btc", "piyasa"],
    )
    service.create_event(
        title="Makro Ozet: USD/TRY 44.34 | EUR/TRY 51.25 | GBP/TRY 59.13",
        summary="USD/TRY 44.34 seviyesinde. XAU/USD 4455.34.",
        category="economy",
        importance=9,
        source="er_api",
        timestamp=now - timedelta(minutes=2),
        tags=["makro", "usdtry", "eurtry", "xauusd"],
    )

    ctx = select_relevant_intel_context(service, "Guncel makro tarafta en onemli tablo ne?", user_id="ayex", max_events=3)

    assert ctx["key_events"]
    assert ctx["key_events"][0]["source"] == "er_api"
    assert "Makro Ozet" in ctx["key_events"][0]["title"]


def test_select_relevant_intel_context_treats_live_inventory_query_as_general_feed_request():
    service = IntelService(IntelStore())
    now = datetime.now(timezone.utc)
    service.create_event(
        title="Kripto Piyasasi: BTC $70.67K | +3.66% (24s)",
        summary="BTC ve SOL guclu.",
        category="economy",
        importance=8,
        source="coingecko",
        timestamp=now - timedelta(minutes=5),
        tags=["kripto", "btc"],
    )
    service.create_event(
        title="Makro Ozet: USD/TRY 44.34 | EUR/TRY 51.25",
        summary="Kur ve altin birlikte yukari.",
        category="economy",
        importance=9,
        source="er_api",
        timestamp=now - timedelta(minutes=3),
        tags=["makro", "usdtry"],
    )
    service.create_event(
        title="Russian attacks kill six in Ukraine, officials say",
        summary="Gece saldirilarinda can kaybi var.",
        category="global",
        importance=8,
        source="bbc_world",
        timestamp=now - timedelta(minutes=20),
        tags=["war", "ukraine"],
    )

    ctx = select_relevant_intel_context(service, "şuan elinde ki canlı veriler nelerdir", user_id="ayex", max_events=5)

    assert ctx["key_events"]
    assert {item["source"] for item in ctx["key_events"]} >= {"coingecko", "er_api", "bbc_world"}
