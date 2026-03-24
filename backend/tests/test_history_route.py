from __future__ import annotations

from types import SimpleNamespace

from backend.src.routes.history import decision_feedback
from backend.src.schemas import DecisionFeedbackRequest
from backend.src.services.decision_history import build_recent_decisions


class _FakeChatStore:
    def __init__(self):
        self.updated = None

    def update_message_metrics(self, session_id: str, message_id: str, metrics_patch: dict):
        self.updated = {
            "id": message_id,
            "session_id": session_id,
            "metrics": dict(metrics_patch or {}),
        }
        return self.updated


def test_decision_feedback_route_updates_message_metrics():
    chat_store = _FakeChatStore()
    services = SimpleNamespace(chat_store=chat_store)

    payload = DecisionFeedbackRequest(outcome_status="dogru", note="Beklenen yone gitti.")
    out = decision_feedback("sess-1", "msg-1", payload, services=services)

    assert out["status"] == "ok"
    assert out["updated"] is True
    assert chat_store.updated is not None
    assert chat_store.updated["metrics"]["decision_feedback"]["outcome_status"] == "dogru"


def test_decision_history_prefers_manual_feedback_over_inferred_outcome():
    class _Store:
        def list_sessions(self, limit: int = 18):
            return [{"id": "sess-1", "title": "Karar", "updated_at": "2026-03-24T10:00:00"}]

        def messages(self, session_id: str, limit: int = 80):
            return [
                {
                    "id": "msg-1",
                    "session_id": session_id,
                    "ts": "2026-03-24T09:00:00",
                    "role": "assistant",
                    "text": "Ahmet, su an en mantikli secenek SOL.",
                    "metrics": {
                        "response_mode": "decision",
                        "source": "model_direct",
                        "decision_feedback": {"outcome_status": "yanlis", "note": "Momentum bozuldu."},
                        "explainability": {
                            "response_mode": "decision",
                            "decision": "Ahmet, su an en mantikli secenek SOL.",
                            "decision_asset": "SOL",
                            "decision_stance": "conviction",
                        },
                    },
                }
            ]

    history = build_recent_decisions(
        _Store(),
        latest_events=[],
        profile_data={},
        limit=4,
    )

    assert history
    assert history[0]["outcome_status"] == "yanlis"
    assert history[0]["outcome_note"] == "Momentum bozuldu."
