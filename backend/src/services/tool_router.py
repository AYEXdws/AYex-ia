from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.src.tools.base import ToolExecution
from backend.src.tools.registry import ToolRegistry
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolRouteResult:
    intent: str
    selected_tool: str = ""
    executions: list[ToolExecution] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return any(x.output is not None and not x.error for x in self.executions)

    def evidence_text(self) -> str:
        if not self.executions:
            return ""
        lines: list[str] = []
        for run in self.executions:
            if run.error:
                lines.append(f"[{run.name}] error={run.error}")
                continue
            lines.append(f"[{run.name}] summary={run.output.summary}")
            lines.append(f"data={run.output.data}")
        return "\n".join(lines)


class ToolRouter:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def route_and_run(self, *, intent: str, text: str, max_calls: int = 2) -> ToolRouteResult:
        if max_calls <= 0:
            return ToolRouteResult(intent=intent)

        if intent == "market":
            # Market data should come from intel feeds; skip live market tool to avoid redundant external calls.
            logger.info("TOOL_SKIPPED=%s intent=%s reason=%s", "market_tool", intent, "intel_feed_preferred")
            return ToolRouteResult(intent=intent)

        if intent == "url_read":
            url = self._extract_url(text)
            run = self.registry.run("fetch_url_tool", query=text, params={"url": url, "max_chars": 5000})
            logger.info("TOOL_SELECTED=%s intent=%s", "fetch_url_tool", intent)
            return ToolRouteResult(intent=intent, selected_tool="fetch_url_tool", executions=[run])

        if intent == "search":
            run = self.registry.run("search_tool", query=text, params={"limit": 5})
            logger.info("TOOL_SELECTED=%s intent=%s", "search_tool", intent)
            return ToolRouteResult(intent=intent, selected_tool="search_tool", executions=[run])

        return ToolRouteResult(intent=intent)

    def run_agent_tools(self, *, text: str, max_calls: int = 3) -> ToolRouteResult:
        executions: list[ToolExecution] = []
        selected: list[str] = []
        candidates = self._agent_candidates(text)
        for tool_name in candidates[: max(1, min(max_calls, 3))]:
            params: dict = {}
            if tool_name == "fetch_url_tool":
                params["url"] = self._extract_url(text)
                params["max_chars"] = 5000
            if tool_name == "search_tool":
                params["limit"] = 5
            run = self.registry.run(tool_name, query=text, params=params)
            executions.append(run)
            selected.append(tool_name)
            logger.info("TOOL_SELECTED=%s intent=%s", tool_name, "agent_task")
        return ToolRouteResult(intent="agent_task", selected_tool=",".join(selected), executions=executions)

    def _extract_url(self, text: str) -> str:
        m = re.search(r"(https?://[^\s]+)", text)
        return m.group(1) if m else ""

    def _agent_candidates(self, text: str) -> list[str]:
        normalized = text.lower()
        out: list[str] = []
        if "http://" in normalized or "https://" in normalized:
            out.append("fetch_url_tool")
        if any(k in normalized for k in ("arastir", "karsilastir", "analiz", "nedir", "kimdir", "haber")):
            out.append("search_tool")
        if not out:
            out.append("search_tool")
        # unique preserve order
        uniq: list[str] = []
        seen: set[str] = set()
        for x in out:
            if x in seen:
                continue
            seen.add(x)
            uniq.append(x)
        return uniq
