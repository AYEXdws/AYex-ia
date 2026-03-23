from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from backend.src.intel.event_model import IntelEvent
from backend.src.routes.intel import intel_brief, public_intel


class _FakeIntel:
    def __init__(self):
        self._events = [
            IntelEvent(
                title="Kripto Piyasasi: BTC $71K | +3.7%",
                summary="BTC: $71K +3.7%, ETH: $2.1K +4.1%, SOL: $91 +4.6%",
                category="economy",
                importance=8,
                source="coingecko",
                tags=["kripto", "btc", "piyasa"],
                timestamp=datetime.utcnow(),
                final_score=0.82,
                confidence_score=0.75,
            ),
            IntelEvent(
                title="Hisse Senetleri: ASML +4.1% | TSLA +3.1%",
                summary="ASML: $1.4K +4.1%, TSLA: $379 +3.1%, AMZN: $211 +3.0%",
                category="economy",
                importance=6,
                source="yahoo_finance",
                tags=["hisse", "borsa", "tech", "asml", "tsla"],
                timestamp=datetime.utcnow(),
                final_score=0.63,
                confidence_score=0.75,
            ),
            IntelEvent(
                title="Makro Ozet: USD/TRY 44.34 | EUR/TRY 48.20 | GBP/TRY 57.10",
                summary="USD/TRY 44.34 seviyesinde. EUR/TRY 48.20, GBP/TRY 57.10.",
                category="economy",
                importance=8,
                source="er_api",
                tags=["makro", "usdtry", "eurtry", "forex"],
                timestamp=datetime.utcnow(),
                final_score=0.67,
                confidence_score=0.75,
            ),
            IntelEvent(
                title="Oracle Patches Critical CVE-2026-21992",
                summary="Critical RCE yamasi yayinlandi.",
                category="security",
                importance=9,
                source="the_hacker_news",
                tags=["cve", "rce", "critical"],
                timestamp=datetime.utcnow() - timedelta(hours=18),
                final_score=0.79,
                confidence_score=0.75,
            ),
        ]
        self.store = SimpleNamespace(get_all_events=lambda: list(self._events))

    def get_daily_brief(self, user_id: str = "default") -> dict:
        _ = user_id
        return {"daily_brief": "Gunluk brief hazir.", "insights": []}

    def get_latest_events(self, limit: int = 10) -> list[IntelEvent]:
        return self._events[:limit]

    def filter_by_user_profile(self, events: list[IntelEvent], user_id: str = "default") -> list[IntelEvent]:
        _ = user_id
        return events


class _FakeServices:
    def __init__(self):
        self.intel = _FakeIntel()
        self.profile = SimpleNamespace(
            load=lambda: {
                "assistant_name": "AYEX",
                "feedback_style": "sert ve net",
                "preferred_categories": ["security", "economy"],
                "focus_projects": ["AYEX-IA"],
            }
        )


def test_intel_brief_includes_market_focus_cards():
    request = SimpleNamespace(state=SimpleNamespace(user_id="ahmet"))
    payload = intel_brief(request, services=_FakeServices())

    assert "Gunluk brief hazir." in payload["proactive"]["summary"]
    assert payload["market_focus"]["crypto"]["active"] is True
    assert payload["market_focus"]["crypto"]["asset"] in {"BTC", "ETH", "SOL"}
    assert payload["market_focus"]["equities"]["active"] is True
    assert payload["market_focus"]["equities"]["asset"] in {"ASML", "TSLA"}
    assert payload["market_focus"]["crypto_signals"]
    assert payload["market_focus"]["equities_signals"]
    assert payload["market_focus"]["macro"]["active"] is True
    assert "Makro Ozet" in payload["market_focus"]["macro"]["summary"]
    assert payload["domain_focus"]["world"]["active"] is False
    assert payload["domain_focus"]["cyber"]["available"] is True
    assert payload["domain_focus"]["cyber"]["freshness_state"] == "watch"
    assert payload["live_inventory"]["feeds"]["crypto"]["available"] is True
    assert payload["live_inventory"]["feeds"]["macro"]["available"] is True
    assert payload["live_inventory"]["feeds"]["cyber"]["available"] is True
    assert payload["persona_focus"]["assistant_name"] == "AYEX"
    assert payload["persona_focus"]["feedback_style"] == "sert ve net"


def test_public_intel_exposes_curated_sections():
    payload = public_intel(services=_FakeServices())

    assert payload["brand"] == "AYEXDWS"
    assert payload["overview"]["stats"]["active_feeds"] >= 2
    assert len(payload["pulse"]) >= 3
    sections = {section["key"]: section for section in payload["sections"]}
    assert {"crypto", "equities", "macro", "world", "cyber"} <= set(sections)
    assert sections["crypto"]["items"]
    assert sections["equities"]["items"]
    assert sections["macro"]["items"]
    assert sections["cyber"]["items"]
