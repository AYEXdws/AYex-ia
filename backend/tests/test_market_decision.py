from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from backend.src.services.market_decision import build_market_decision, enforce_decision_reply
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


def test_market_decision_parses_aggregate_crypto_snapshot():
    latest_events = [
        SimpleNamespace(
            title="Kripto Piyasasi: BTC $70.91K | +2.96% (24s)",
            summary=(
                "Top 5: BTC: $70.91K (+2.96%) | ETH: $2.16K (+4.09%) | XRP: $1.4600 (+4.55%) | "
                "BNB: $643.3800 (+2.04%) | SOL: $91.2000 (+4.46%). "
                "En cok yukselen: XRP +4.55%. En cok dusen: TRX -2.99%."
            ),
            tags=["kripto", "btc", "piyasa"],
            importance=7,
            final_score=0.67,
            timestamp=datetime.utcnow(),
        )
    ]

    out = build_market_decision(text="1 ay icin hangi coin daha mantikli", latest_events=latest_events)

    assert out.active is True
    assert out.asset in {"XRP", "SOL", "ETH"}
    assert out.summary.startswith("Ahmet, su an")


def test_market_decision_parses_stock_snapshot_in_equity_scope():
    latest_events = [
        SimpleNamespace(
            title="Hisse Senetleri: ASML: $1.4K (+4.08%) | TSLA: $379.47 (+3.13%) | AMZN: $211.48 (+2.98%)",
            summary=(
                "Tech/global hisseler: ASML: $1.4K +4.08%, TSLA: $379.47 +3.13%, AMZN: $211.48 +2.98%, CRM: $193.40 -1.01%. "
                "En buyuk hareket: ASML +4.08%. Yukselenler: ASML, TSLA, AMZN. Dusenler: CRM."
            ),
            tags=["hisse", "borsa", "tech", "asml"],
            importance=6,
            final_score=0.62,
            timestamp=datetime.utcnow(),
        )
    ]

    out = build_market_decision(text="1 ay icin hangi hisse daha mantikli", latest_events=latest_events)

    assert out.active is True
    assert out.asset == "ASML"
    assert out.stance in {"buy", "watch"}


def test_market_decision_understands_named_crypto_movers():
    latest_events = [
        SimpleNamespace(
            title="Kripto Piyasasi: BTC $70.91K | +2.96% (24s)",
            summary=(
                "Top 5: BTC: $70.91K (+2.96%) | ETH: $2.16K (+4.09%) | XRP: $1.4600 (+4.55%) | "
                "BNB: $643.3800 (+2.04%) | SOL: $91.2000 (+4.46%). "
                "En cok yukselen: SHIB +5.66%. En cok dusen: TRX -2.99%."
            ),
            tags=["kripto", "btc", "piyasa"],
            importance=7,
            final_score=0.67,
            timestamp=datetime.utcnow(),
        )
    ]

    out = build_market_decision(text="1 ay icin hangi coin daha mantikli", latest_events=latest_events)

    assert out.active is True
    assert out.asset in {"SHIB", "XRP", "SOL", "ETH"}


def test_enforce_decision_reply_prepends_clear_headline():
    decision = {
        "active": True,
        "asset": "SOL",
        "stance": "buy",
        "summary": "Ahmet, su an en mantikli secenek SOL.",
        "reasons": ["Momentum daha temiz.", "Kanit daha taze."],
        "risks": ["Ani geri cekilme riski var."],
    }

    out = enforce_decision_reply(decision=decision, reply="Momentum daha temiz ve kanit daha taze duruyor.", strict=True)

    assert out.startswith("Ahmet, su an en mantikli secenek SOL.")
    assert "Neden:" in out
    assert "Risk:" in out


def test_enforce_decision_reply_strips_repeated_headline_from_model_text():
    decision = {
        "active": True,
        "asset": "SOL",
        "stance": "buy",
        "summary": "Ahmet, su an en mantikli secenek SOL.",
        "reasons": ["Momentum daha temiz."],
        "risks": ["Ani geri cekilme riski var."],
    }

    out = enforce_decision_reply(
        decision=decision,
        reply=(
            "Ahmet, su an en mantikli secenek SOL.\n\n"
            "SOL 1 aylik pencerede daha guclu momentum tasiyor."
        ),
        strict=True,
    )

    assert out.count("Ahmet, su an en mantikli secenek SOL.") == 1
    assert "SOL 1 aylik pencerede daha guclu momentum tasiyor." in out


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
