from __future__ import annotations

import json
from urllib import request as urlrequest

from backend.src.tools.base import ToolExecution, ToolInput, ToolOutput
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


class MarketTool:
    name = "market_tool"

    def run(self, tool_input: ToolInput) -> ToolExecution:
        try:
            crypto = self._fetch_json(
                "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd,try"
            )
            fx = self._fetch_json("https://open.er-api.com/v6/latest/USD")
            xau = self._fetch_json("https://api.metals.live/v1/spot/gold")

            usd_try = float((fx.get("rates") or {}).get("TRY"))
            btc = float((crypto.get("bitcoin") or {}).get("usd"))
            eth = float((crypto.get("ethereum") or {}).get("usd"))

            gold_usd_oz = 0.0
            if isinstance(xau, list) and xau and isinstance(xau[0], dict):
                gold_usd_oz = float(xau[0].get("gold") or 0.0)

            payload = {
                "BTC_USD": btc,
                "ETH_USD": eth,
                "USD_TRY": usd_try,
                "XAU_USD_OZ": gold_usd_oz,
            }
            summary = "Piyasa verileri guncellendi."
            return ToolExecution(
                name=self.name,
                input=tool_input,
                output=ToolOutput(data=payload, summary=summary),
                error=None,
            )
        except Exception as exc:
            logger.warning("MARKET_TOOL_FAILED error=%s", str(exc))
            return ToolExecution(
                name=self.name,
                input=tool_input,
                output=ToolOutput(data={}, summary="Canli piyasa verisine ulasilamadi."),
                error=None,
            )

    def _fetch_json(self, url: str) -> dict | list:
        req = urlrequest.Request(url, headers={"User-Agent": "AYEX-IA/1.0"})
        with urlrequest.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
