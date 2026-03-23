from __future__ import annotations

import ipaddress
import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from urllib.parse import urlparse

from backend.src.tools.base import ToolExecution, ToolInput, ToolOutput
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
        max_chars = 2200
        used = 0
        lines: list[str] = []
        for run in self.executions:
            if run.error:
                row = f"[{run.name}] error={str(run.error)[:220]}"
                if used + len(row) > max_chars:
                    break
                lines.append(row)
                used += len(row)
                continue
            summary = str(run.output.summary)[:240]
            try:
                data_blob = json.dumps(run.output.data, ensure_ascii=False)
            except Exception:
                data_blob = str(run.output.data)
            data_blob = data_blob[:1200]
            row1 = f"[{run.name}] summary={summary}"
            row2 = f"data={data_blob}"
            if used + len(row1) > max_chars:
                break
            lines.append(row1)
            used += len(row1)
            if used + len(row2) > max_chars:
                break
            lines.append(row2)
            used += len(row2)
        return "\n".join(lines)


class ToolRouter:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._allowed_tools = {"search_tool", "fetch_url_tool", "market_tool"}
        self._timeout_sec = 8.0
        self._max_data_chars = 2200
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool-router")

    def route_and_run(self, *, intent: str, text: str, max_calls: int = 2) -> ToolRouteResult:
        if max_calls <= 0:
            return ToolRouteResult(intent=intent)

        if intent == "market":
            # Market data should come from intel feeds; skip live market tool to avoid redundant external calls.
            logger.info("TOOL_SKIPPED=%s intent=%s reason=%s", "market_tool", intent, "intel_feed_preferred")
            return ToolRouteResult(intent=intent)

        if intent == "url_read":
            url = self._extract_url(text)
            if not self._is_allowed_url(url):
                run = ToolExecution(
                    name="fetch_url_tool",
                    input=ToolInput(query=text, params={"url": url}),
                    output=None,
                    error="url_not_allowed",
                )
            else:
                run = self._run_tool("fetch_url_tool", query=text, params={"url": url, "max_chars": 3000})
            logger.info("TOOL_SELECTED=%s intent=%s", "fetch_url_tool", intent)
            return ToolRouteResult(intent=intent, selected_tool="fetch_url_tool", executions=[run])

        if intent == "search":
            run = self._run_tool("search_tool", query=text, params={"limit": 5})
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
                params["max_chars"] = 3000
                if not self._is_allowed_url(str(params["url"] or "")):
                    run = ToolExecution(
                        name=tool_name,
                        input=ToolInput(query=text, params=params),
                        output=None,
                        error="url_not_allowed",
                    )
                    executions.append(run)
                    selected.append(tool_name)
                    logger.info("TOOL_SELECTED=%s intent=%s", tool_name, "agent_task")
                    continue
            if tool_name == "search_tool":
                params["limit"] = 5
            run = self._run_tool(tool_name, query=text, params=params)
            executions.append(run)
            selected.append(tool_name)
            logger.info("TOOL_SELECTED=%s intent=%s", tool_name, "agent_task")
        return ToolRouteResult(intent="agent_task", selected_tool=",".join(selected), executions=executions)

    def _extract_url(self, text: str) -> str:
        m = re.search(r"(https?://[^\s]+)", text)
        return m.group(1) if m else ""

    def _is_allowed_url(self, url: str) -> bool:
        raw = str(url or "").strip()
        if not raw:
            return False
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = str(parsed.hostname or "").strip().lower()
        if not host:
            return False
        if host in {"localhost"} or host.endswith(".local"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        except ValueError:
            pass
        return True

    def _run_tool(self, name: str, *, query: str, params: dict) -> ToolExecution:
        safe_query = str(query or "")[:1600]
        safe_params = dict(params or {})
        if name not in self._allowed_tools:
            return ToolExecution(
                name=name,
                input=ToolInput(query=safe_query, params=safe_params),
                output=None,
                error="tool_not_allowed",
            )

        if name == "search_tool":
            safe_params["limit"] = max(1, min(8, int(safe_params.get("limit", 5) or 5)))
        if name == "fetch_url_tool":
            safe_params["max_chars"] = max(400, min(4000, int(safe_params.get("max_chars", 3000) or 3000)))

        future = self._pool.submit(self.registry.run, name, safe_query, safe_params)
        try:
            run = future.result(timeout=self._timeout_sec)
        except FuturesTimeoutError:
            return ToolExecution(
                name=name,
                input=ToolInput(query=safe_query, params=safe_params),
                output=None,
                error=f"tool_timeout_{int(self._timeout_sec)}s",
            )
        except Exception as exc:
            return ToolExecution(
                name=name,
                input=ToolInput(query=safe_query, params=safe_params),
                output=None,
                error=f"tool_execution_error:{str(exc)[:180]}",
            )

        if run.output is None:
            return run
        summary = str(run.output.summary or "")[:260]
        data = run.output.data
        try:
            data_blob = json.dumps(data, ensure_ascii=False)
        except Exception:
            data_blob = str(data)
        if len(data_blob) > self._max_data_chars:
            data = {
                "truncated": True,
                "preview": data_blob[: self._max_data_chars],
            }
        return ToolExecution(
            name=run.name,
            input=run.input,
            output=ToolOutput(data=data, summary=summary),
            error=run.error,
        )

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
