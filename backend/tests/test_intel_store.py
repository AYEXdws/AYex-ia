from __future__ import annotations

import json
from datetime import datetime

from backend.src.intel.event_model import IntelEvent
from backend.src.intel.intel_archive import IntelArchive
from backend.src.intel.intel_store import IntelStore


def test_intel_store_restores_from_archive_and_persists(tmp_path):
    archive = IntelArchive(data_dir=tmp_path)
    event = IntelEvent(
        title="BTC update",
        summary="btc hareketi",
        category="economy",
        importance=7,
        timestamp=datetime.utcnow(),
        source="coingecko",
    )
    archive.archive_event(event)

    persist_path = tmp_path / "intel_events.json"
    assert not persist_path.exists()

    store = IntelStore(persist_path=persist_path, archive=archive)
    restored = store.get_all_events()

    assert len(restored) == 1
    assert restored[0].title == "BTC update"
    assert persist_path.exists()

    rows = json.loads(persist_path.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["title"] == "BTC update"
