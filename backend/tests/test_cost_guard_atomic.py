from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from backend.src.services.cost_guard import CostGuardService

from conftest import make_settings


def test_cost_guard_is_thread_safe_and_atomic(tmp_path):
    settings = make_settings(tmp_path)
    guard = CostGuardService(settings)

    def _hit():
        return guard.check_and_track("btc")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: _hit(), range(25)))

    assert all(r.ok for r in results)
    usage = guard.usage_today()
    assert int(usage.get("requests", 0)) == 25
    assert int(usage.get("input_chars", 0)) >= 25 * 3
