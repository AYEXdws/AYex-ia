from __future__ import annotations

import time

from backend.src.services.tool_router import ToolRouter
from backend.src.tools.base import ToolExecution, ToolInput, ToolOutput


class _RegistryTimeout:
    def run(self, name: str, query: str, params: dict | None = None) -> ToolExecution:
        _ = (name, query, params)
        time.sleep(0.2)
        return ToolExecution(name="search_tool", input=ToolInput(query=query, params=params or {}), output=ToolOutput(data=[], summary="ok"))


class _RegistryHuge:
    def run(self, name: str, query: str, params: dict | None = None) -> ToolExecution:
        _ = (query, params)
        huge = {"blob": "x" * 10000}
        return ToolExecution(name=name, input=ToolInput(query=query, params=params or {}), output=ToolOutput(data=huge, summary="s" * 500))


def test_tool_router_blocks_private_url():
    router = ToolRouter(_RegistryHuge())

    out = router.route_and_run(intent="url_read", text="http://localhost:8000/test")

    assert out.executions
    assert out.executions[0].error == "url_not_allowed"


def test_tool_router_enforces_timeout_on_tool_execution():
    router = ToolRouter(_RegistryTimeout())
    router._timeout_sec = 0.01

    out = router.route_and_run(intent="search", text="bitcoin")

    assert out.executions
    assert str(out.executions[0].error or "").startswith("tool_timeout")


def test_tool_router_truncates_large_tool_output():
    router = ToolRouter(_RegistryHuge())

    out = router.route_and_run(intent="search", text="btc")

    assert out.executions
    run = out.executions[0]
    assert run.output is not None
    assert isinstance(run.output.data, dict)
    assert run.output.data.get("truncated") is True
