from __future__ import annotations

from datetime import datetime, timedelta

from backend.src.intel.event_model import IntelEvent
from backend.src.intel.intel_store import IntelStore


def test_intel_store_rejects_same_source_same_title_within_day(tmp_path):
    store = IntelStore(persist_path=tmp_path / "intel_events.json")
    ts = datetime.utcnow()
    first = IntelEvent(
        title="We Found Eight Attack Vectors Inside AWS Bedrock. Here's What Attackers Can Do with Them",
        summary="summary one",
        category="security",
        importance=6,
        timestamp=ts,
        source="the_hacker_news",
    )
    duplicate = IntelEvent(
        title="We Found Eight Attack Vectors Inside AWS Bedrock. Here's What Attackers Can Do with Them",
        summary="summary two",
        category="security",
        importance=6,
        timestamp=ts + timedelta(minutes=5),
        source="the_hacker_news",
    )

    assert store.add_event(first) is not None
    assert store.add_event(duplicate) is None


def test_intel_store_rejects_market_snapshots_with_same_signature(tmp_path):
    store = IntelStore(persist_path=tmp_path / "intel_events.json")
    ts = datetime.utcnow()
    first = IntelEvent(
        title="Kripto Piyasasi: BTC $70.77K | +2.90% (24s)",
        summary="btc summary",
        category="economy",
        importance=7,
        timestamp=ts,
        source="coingecko",
    )
    duplicate = IntelEvent(
        title="Kripto Piyasasi: BTC $70.91K | +2.96% (24s)",
        summary="btc summary later",
        category="economy",
        importance=7,
        timestamp=ts + timedelta(minutes=10),
        source="coingecko",
    )

    assert store.add_event(first) is not None
    assert store.add_event(duplicate) is None
