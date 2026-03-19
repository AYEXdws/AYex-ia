from __future__ import annotations

import re
from html import unescape
from urllib import request as urlrequest

from backend.src.tools.base import ToolExecution, ToolInput, ToolOutput


class FetchUrlTool:
    name = "fetch_url_tool"

    def run(self, tool_input: ToolInput) -> ToolExecution:
        url = (tool_input.params.get("url") or tool_input.query or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            return ToolExecution(name=self.name, input=tool_input, output=None, error="Invalid URL")
        try:
            req = urlrequest.Request(url, headers={"User-Agent": "AYEX-IA/1.0"})
            with urlrequest.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            text = self._html_to_text(html)
            max_chars = max(600, min(12000, int(tool_input.params.get("max_chars", 4000) or 4000)))
            content = text[:max_chars]
            summary = "URL icerigi alindi."
            return ToolExecution(
                name=self.name,
                input=tool_input,
                output=ToolOutput(data={"url": url, "text": content}, summary=summary),
                error=None,
            )
        except Exception as exc:
            return ToolExecution(name=self.name, input=tool_input, output=None, error=str(exc))

    def _html_to_text(self, html: str) -> str:
        stripped = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        stripped = re.sub(r"(?is)<style.*?>.*?</style>", " ", stripped)
        stripped = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", stripped)
        stripped = re.sub(r"(?is)<[^>]+>", " ", stripped)
        stripped = unescape(stripped)
        return " ".join(stripped.split())
