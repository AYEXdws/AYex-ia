from __future__ import annotations

from dataclasses import dataclass

from backend.src.services.model_service import ModelService
from backend.src.services.openai_client import OpenAIChatResult

from conftest import make_settings


@dataclass
class _Recorder:
    last_kwargs: dict | None = None

    def call_responses(self, **kwargs):
        self.last_kwargs = dict(kwargs)
        return OpenAIChatResult(
            text="ok",
            used_model=str(kwargs.get("model") or ""),
            latency_ms=11,
            raw={"usage": {"input_tokens": 12, "output_tokens": 7}},
        )


def test_model_service_omits_temperature_for_gpt5(tmp_path):
    settings = make_settings(tmp_path)
    service = ModelService(settings)
    recorder = _Recorder()
    service.openai = recorder  # type: ignore[assignment]

    result = service.run_action(text="uzun vade strateji", model="gpt-5", route_name="test")

    assert result.ok is True
    assert recorder.last_kwargs is not None
    assert "temperature" in recorder.last_kwargs
    assert recorder.last_kwargs["temperature"] is None


def test_model_service_sets_temperature_for_non_gpt5(tmp_path):
    settings = make_settings(tmp_path)
    service = ModelService(settings)
    recorder = _Recorder()
    service.openai = recorder  # type: ignore[assignment]

    result = service.run_action(text="merhaba", model="gpt-4o", route_name="test")

    assert result.ok is True
    assert recorder.last_kwargs is not None
    assert recorder.last_kwargs["temperature"] == 0.2
