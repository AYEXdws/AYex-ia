from __future__ import annotations

from types import SimpleNamespace

from backend.src.services.memory_summarizer import MemorySummarizer

from conftest import make_settings


class _FakeOpenAI:
    def call_responses(self, **kwargs):
        _ = kwargs
        return SimpleNamespace(text="Kullanici kripto ve guvenlik konusunda kisa bir analiz istedi.")


def test_memory_retry_queue_processes_and_stores(tmp_path):
    settings = make_settings(tmp_path)
    memory = MemorySummarizer(settings)
    messages = [
        {"role": "user", "text": "BTC ne durumda"},
        {"role": "assistant", "text": "Dususte ama takip gerekli"},
    ]

    queued = memory.queue_retry(session_id="s1", messages=messages, reason="model_timeout")
    assert queued is True

    processed = memory.process_retry_queue(openai_client=_FakeOpenAI(), max_items=2)
    assert processed >= 1

    context = memory.get_memory_context("btc")
    assert context
    assert "KONU" in context.upper() or "BTC" in context.upper()
