from __future__ import annotations

import re
from html import unescape
from urllib import parse as urlparse
from urllib import request as urlrequest

from backend.src.tools.base import ToolExecution, ToolInput, ToolOutput


class SearchTool:
    name = "search_tool"

    def run(self, tool_input: ToolInput) -> ToolExecution:
        query = (tool_input.query or "").strip()
        if not query:
            return ToolExecution(name=self.name, input=tool_input, output=None, error="Empty query")
        try:
            endpoint = f"https://duckduckgo.com/html/?q={urlparse.quote_plus(query)}"
            req = urlrequest.Request(
                endpoint,
                headers={"User-Agent": "AYEX-IA/1.0"},
            )
            with urlrequest.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            rows = self._extract_rows(html, limit=int(tool_input.params.get("limit", 5) or 5))
            summary = "Arama sonucu bulunamadi." if not rows else f"{len(rows)} sonuc bulundu."
            return ToolExecution(
                name=self.name,
                input=tool_input,
                output=ToolOutput(data=rows, summary=summary),
                error=None,
            )
        except Exception as exc:
            return ToolExecution(name=self.name, input=tool_input, output=None, error=str(exc))

    def _extract_rows(self, html: str, limit: int = 5) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="(?P<link>[^"]+)"[^>]*>(?P<title>.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for m in pattern.finditer(html):
            link = self._clean_html(m.group("link"))
            title = self._clean_html(m.group("title"))
            if not link or not title:
                continue
            out.append({"title": title, "link": link, "snippet": ""})
            if len(out) >= max(1, min(10, limit)):
                break
        return out

    def _clean_html(self, text: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", text or "")
        cleaned = unescape(cleaned)
        return " ".join(cleaned.split())
