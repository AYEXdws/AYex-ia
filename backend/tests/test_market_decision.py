from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from backend.src.services.market_decision import build_market_decision
from backend.src.services.proactive_briefing import build_proactive_briefing


def test_market_decision_prefers_asset_with_cleaner_positive_flow():
    intel_context = {
        "key_events": [
            {
                "title": "Solana sees strong inflow and breakout",
                "summary": "SOL continues rally with fresh accumulation",
                "tags": ["sol", "market"],
                "importance": 8,
                "effective_score": 0.92,
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "title": "XRP faces lawsuit volatility",
                "summary": "XRP remains under pressure after weak reaction",
                "tags": ["xrp"],
                "importance": 7,
                "effective_score": 0.71,
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]
    }

    out = build_market_decision(text="1 ay icin hangi coin daha mantikli", intel_context=intel_context)

    assert out.active is True
    assert out.asset == "SOL"
    assert out.stance in {"buy", "watch"}


def test_proactive_briefing_returns_compare_and_priorities():
    now = datetime.utcnow()
    intel = SimpleNamespace(
        get_latest_events=lambda limit=6: [
            SimpleNamespace(
                title="BTC jumps after ETF inflow",
                timestamp=now,
                category="economy",
                tags=["btc"],
            ),
            SimpleNamespace(
                title="NVIDIA chip update shifts AI pricing",
                timestamp=now,
                category="tech",
                tags=["ai", "nvda"],
            ),
        ],
        get_daily_brief=lambda user_id="default": {
            "daily_brief": "Bugun macro ve AI tarafinda hareket var.",
            "insights": [],
        },
    )

    out = build_proactive_briefing(intel, user_id="ayex", limit=6)

    assert out["summary"]
    assert out["priorities"]
