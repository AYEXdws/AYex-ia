from __future__ import annotations

from backend.src.tools.base import Tool, ToolExecution, ToolInput
from backend.src.tools.fetch_url_tool import FetchUrlTool
from backend.src.tools.market_tool import MarketTool
from backend.src.tools.search_tool import SearchTool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {
            "search_tool": SearchTool(),
            "fetch_url_tool": FetchUrlTool(),
            "market_tool": MarketTool(),
        }

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def run(self, name: str, query: str, params: dict | None = None) -> ToolExecution:
        tool = self._tools.get(name)
        tool_input = ToolInput(query=query, params=params or {})
        if tool is None:
            return ToolExecution(name=name, input=tool_input, output=None, error=f"Unknown tool: {name}")
        return tool.run(tool_input)
