from __future__ import annotations

from backend.src.services.query_context import detect_response_mode


def test_detect_response_mode_marks_live_inventory_queries():
    out = detect_response_mode(
        "su an elinde hangi canli veriler var",
        intent_category="chat",
        response_style="normal",
    )

    assert out == "inventory"


def test_detect_response_mode_marks_market_decision_queries():
    out = detect_response_mode(
        "1 ay icin hangi coin daha mantikli",
        intent_category="market",
        response_style="brief",
    )

    assert out == "decision"


def test_detect_response_mode_marks_analysis_queries():
    out = detect_response_mode(
        "bu sistemi stratejik olarak analiz et ve riskleri cikar",
        intent_category="agent_task",
        response_style="deep",
    )

    assert out == "analysis"
