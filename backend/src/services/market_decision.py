from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any


ASSET_ALIASES: dict[str, tuple[str, ...]] = {
    "BTC": ("btc", "bitcoin"),
    "ETH": ("eth", "ethereum"),
    "SOL": ("sol", "solana"),
    "XRP": ("xrp", "ripple"),
    "BNB": ("bnb", "binance"),
    "SUI": ("sui",),
    "DOGE": ("doge", "dogecoin"),
    "ADA": ("ada", "cardano"),
    "AVAX": ("avax", "avalanche"),
    "LINK": ("link", "chainlink"),
    "DOT": ("dot", "polkadot"),
    "UNI": ("uni", "uniswap"),
    "NEAR": ("near",),
    "ICP": ("icp", "internet computer"),
    "APT": ("apt", "aptos"),
    "FIL": ("fil", "filecoin"),
    "VET": ("vet", "vechain"),
    "LTC": ("ltc", "litecoin"),
    "XLM": ("xlm", "stellar"),
    "TRX": ("trx", "tron"),
    "SHIB": ("shib", "shiba", "shiba inu"),
    "AAPL": ("aapl", "apple"),
    "NVDA": ("nvda", "nvidia"),
    "TSLA": ("tsla", "tesla"),
    "MSFT": ("msft", "microsoft"),
    "GOOGL": ("googl", "google", "alphabet"),
    "AMZN": ("amzn", "amazon"),
    "ASML": ("asml",),
    "TSM": ("tsm",),
    "BABA": ("baba", "alibaba"),
    "CRM": ("crm", "salesforce"),
    "AMD": ("amd",),
    "INTC": ("intc", "intel"),
    "ORCL": ("orcl", "oracle"),
}
CRYPTO_ASSETS = {"BTC", "ETH", "SOL", "XRP", "BNB", "SUI", "DOGE", "ADA", "AVAX", "LINK", "DOT", "UNI", "NEAR", "ICP", "APT", "FIL", "VET", "LTC", "XLM", "TRX", "SHIB"}
EQUITY_ASSETS = set(ASSET_ALIASES) - CRYPTO_ASSETS

POSITIVE_MARKERS = (
    "inflow",
    "approval",
    "breakout",
    "surge",
    "strong",
    "buy",
    "accumulation",
    "record",
    "growth",
    "adoption",
    "launch",
    "partnership",
    "rally",
    "uptrend",
    "yukselen",
    "en cok yukselen",
    "en buyuk hareket",
    "top 5",
)

NEGATIVE_MARKERS = (
    "hack",
    "breach",
    "exploit",
    "outflow",
    "sell",
    "dump",
    "lawsuit",
    "ban",
    "crash",
    "weak",
    "volatility",
    "liquidation",
    "delist",
    "bearish",
    "dusenler",
    "en cok dusen",
)


@dataclass(frozen=True)
class MarketDecision:
    active: bool = False
    asset: str = ""
    stance: str = "wait"
    confidence: float = 0.0
    summary: str = ""
    reasons: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "asset": self.asset,
            "stance": self.stance,
            "confidence": round(float(self.confidence or 0.0), 3),
            "summary": self.summary,
            "reasons": list(self.reasons),
            "risks": list(self.risks),
            "evidence": list(self.evidence),
        }


def build_market_decision(*, text: str, intel_context: dict[str, Any] | None = None, latest_events: list[Any] | None = None) -> MarketDecision:
    normalized = _normalize(text)
    if not _is_market_decision_query(normalized):
        return MarketDecision()
    scope = _detect_scope(normalized)

    candidate_scores: dict[str, float] = {}
    candidate_reasons: dict[str, list[str]] = {}
    candidate_risks: dict[str, list[str]] = {}
    candidate_evidence: dict[str, list[str]] = {}

    explicit_assets = _assets_in_text(normalized)
    if explicit_assets:
        for asset in explicit_assets:
            if not _asset_in_scope(asset, scope):
                continue
            candidate_scores.setdefault(asset, 0.2)

    key_events = list((intel_context or {}).get("key_events") or [])
    for item in key_events:
        _score_event(
            item,
            scope=scope,
            candidate_scores=candidate_scores,
            candidate_reasons=candidate_reasons,
            candidate_risks=candidate_risks,
            candidate_evidence=candidate_evidence,
        )

    for event in list(latest_events or [])[:12]:
        payload = {
            "title": str(getattr(event, "title", "") or "").strip(),
            "summary": str(getattr(event, "summary", "") or "").strip(),
            "tags": list(getattr(event, "tags", []) or []),
            "importance": int(getattr(event, "importance", 5) or 5),
            "effective_score": float(getattr(event, "final_score", 0.0) or 0.0),
            "timestamp": getattr(event, "timestamp", None).isoformat() if hasattr(getattr(event, "timestamp", None), "isoformat") else "",
        }
        _score_event(
            payload,
            scope=scope,
            candidate_scores=candidate_scores,
            candidate_reasons=candidate_reasons,
            candidate_risks=candidate_risks,
            candidate_evidence=candidate_evidence,
        )

    if not candidate_scores:
        return MarketDecision(
            active=True,
            stance="wait",
            summary="Ahmet, su an net edge yok. Karar verecek kadar temiz market kaniti birikmemis durumda.",
            reasons=("Piyasaya dair acik bir ustunluk sinyali cikmadi.",),
            risks=("Gereksiz zorlanmis secim yapma riski var.",),
        )

    ordered = sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)
    top_asset, top_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else -999.0
    margin = top_score - second_score
    top_risks = tuple(candidate_risks.get(top_asset, [])[:2])
    top_reasons = tuple(candidate_reasons.get(top_asset, [])[:3])
    top_evidence = tuple(candidate_evidence.get(top_asset, [])[:3])

    if top_score < 1.15 or (margin < 0.2 and top_score < 1.6):
        return MarketDecision(
            active=True,
            stance="wait",
            confidence=min(0.52, max(0.18, top_score / 3.0)),
            summary=f"Ahmet, su an tek bir varligi zorla one cikarmak dogru degil. {top_asset} hafif onde ama edge yeterince temiz degil.",
            reasons=top_reasons or (f"{top_asset} digerlerine gore hafif daha iyi gozukuyor.",),
            risks=top_risks or ("Momentumun kirilgan olma ihtimali var.",),
            evidence=top_evidence,
        )

    stance = "buy" if top_score >= 1.55 else "watch"
    if stance == "buy":
        summary = f"Ahmet, su an en mantikli secenek {top_asset}."
    else:
        summary = f"Ahmet, su an izlemeye en deger aday {top_asset}, ama giris icin biraz daha teyit iyi olur."
    confidence = min(0.93, max(0.34, 0.46 + (top_score / 4.2)))
    return MarketDecision(
        active=True,
        asset=top_asset,
        stance=stance,
        confidence=confidence,
        summary=summary,
        reasons=top_reasons or (f"{top_asset} lehine daha guclu guncel sinyal var.",),
        risks=top_risks or ("Kisa vadede ani ters hareket riski devam ediyor.",),
        evidence=top_evidence,
    )


def build_decision_prompt_block(decision: dict[str, Any] | None) -> str:
    row = dict(decision or {})
    if not row.get("active"):
        return ""
    parts = [f"Hukum: {str(row.get('summary') or '').strip()}"]
    reasons = [str(item).strip() for item in (row.get("reasons") or []) if str(item).strip()]
    risks = [str(item).strip() for item in (row.get("risks") or []) if str(item).strip()]
    evidence = [str(item).strip() for item in (row.get("evidence") or []) if str(item).strip()]
    if reasons:
        parts.append("Gerekceler:\n- " + "\n- ".join(reasons[:3]))
    if risks:
        parts.append("Temel risk:\n- " + "\n- ".join(risks[:2]))
    if evidence:
        parts.append("Kanit:\n- " + "\n- ".join(evidence[:3]))
    return "\n\n".join(parts).strip()


def enforce_decision_reply(*, decision: dict[str, Any] | None, reply: str, strict: bool = False) -> str:
    row = dict(decision or {})
    text = str(reply or "").strip()
    if not row.get("active"):
        return text
    stance = str(row.get("stance") or "wait").strip().lower()
    asset = str(row.get("asset") or "").strip()
    if stance == "buy" and asset:
        headline = f"Ahmet, su an en mantikli secenek {asset}."
    elif stance == "watch" and asset:
        headline = f"Ahmet, su an izlemeye en deger aday {asset}, ama giris icin acele etme."
    else:
        headline = "Ahmet, su an net edge yok. Beklemek daha dogru."
    reasons = [str(item).strip() for item in (row.get("reasons") or []) if str(item).strip()]
    risks = [str(item).strip() for item in (row.get("risks") or []) if str(item).strip()]
    normalized_headline = _normalize(headline)
    base_lines = [headline]
    if reasons:
        base_lines.append("Neden: " + " ".join(reasons[:2]))
    if risks:
        base_lines.append("Risk: " + risks[0])

    if not text:
        return "\n".join(base_lines)

    if strict:
        if _normalize(text).startswith(normalized_headline):
            return "\n".join(base_lines + ([text] if len(text) > len(headline) + 12 else []))
        return "\n".join(base_lines + [text])

    if _normalize(text).startswith(normalized_headline):
        return text
    return f"{headline}\n\n{text}" if text else headline


def is_market_decision_query(text: str) -> bool:
    return _is_market_decision_query(_normalize(text))


def _score_event(
    item: dict[str, Any],
    *,
    scope: str,
    candidate_scores: dict[str, float],
    candidate_reasons: dict[str, list[str]],
    candidate_risks: dict[str, list[str]],
    candidate_evidence: dict[str, list[str]],
) -> None:
    title = str(item.get("title") or "").strip()
    summary = str(item.get("summary") or "").strip()
    tags = [str(tag).strip() for tag in (item.get("tags") or []) if str(tag).strip()]
    payload = _normalize(" ".join([title, summary, " ".join(tags)]))
    if not payload:
        return

    event_assets = _assets_in_text(payload)
    aggregate_text = " ".join([title, summary])
    aggregate_signals = _extract_asset_change_signals(aggregate_text)
    aggregate_signals.extend(_extract_relative_movers(aggregate_text))
    if not event_assets:
        event_assets = [signal["asset"] for signal in aggregate_signals]
        if not event_assets:
            return

    raw_score = float(item.get("effective_score") or item.get("score") or 0.45)
    importance = max(1, min(10, int(item.get("importance", 5) or 5)))
    freshness = _freshness_multiplier(item.get("timestamp"))
    score_unit = max(0.24, raw_score) * freshness * (0.75 + (importance / 20.0))

    positive_hits = sum(marker in payload for marker in POSITIVE_MARKERS)
    negative_hits = sum(marker in payload for marker in NEGATIVE_MARKERS)
    sentiment = (positive_hits * 0.34) - (negative_hits * 0.42)
    total_score = score_unit + sentiment

    for asset in event_assets:
        if not _asset_in_scope(asset, scope):
            continue
        candidate_scores[asset] = candidate_scores.get(asset, 0.0) + total_score
        candidate_evidence.setdefault(asset, [])
        if title and title not in candidate_evidence[asset]:
            candidate_evidence[asset].append(title)
        if positive_hits > 0:
            candidate_reasons.setdefault(asset, [])
            candidate_reasons[asset].append(f"{asset} ile ilgili pozitif ve taze akış var.")
        if negative_hits > 0:
            candidate_risks.setdefault(asset, [])
            candidate_risks[asset].append(f"{asset} tarafinda negatif risk haberleri de var.")

    for signal in aggregate_signals:
        asset = signal["asset"]
        if not _asset_in_scope(asset, scope):
            continue
        pct = float(signal["change_pct"])
        bonus = min(1.15, abs(pct) / 3.6)
        candidate_scores[asset] = candidate_scores.get(asset, 0.0) + (bonus if pct >= 0 else -bonus)
        candidate_evidence.setdefault(asset, [])
        evidence_line = f"{asset} {pct:+.2f}% hareket"
        if evidence_line not in candidate_evidence[asset]:
            candidate_evidence[asset].append(evidence_line)
        if pct >= 0:
            candidate_reasons.setdefault(asset, [])
            candidate_reasons[asset].append(f"{asset} tarafinda fiyat akisi pozitif ({pct:+.2f}%).")
        else:
            candidate_risks.setdefault(asset, [])
            candidate_risks[asset].append(f"{asset} tarafinda fiyat akisi negatif ({pct:+.2f}%).")

    mover = _extract_named_mover(aggregate_text, positive=True)
    if mover and _asset_in_scope(mover["asset"], scope):
        asset = mover["asset"]
        pct = float(mover["change_pct"])
        candidate_scores[asset] = candidate_scores.get(asset, 0.0) + min(1.25, 0.42 + (abs(pct) / 4.0))
        candidate_reasons.setdefault(asset, [])
        candidate_reasons[asset].append(f"{asset} snapshot icinde en guclu momentum olarak isaretlenmis ({pct:+.2f}%).")

    loser = _extract_named_mover(aggregate_text, positive=False)
    if loser and _asset_in_scope(loser["asset"], scope):
        asset = loser["asset"]
        pct = float(loser["change_pct"])
        candidate_scores[asset] = candidate_scores.get(asset, 0.0) - min(1.15, 0.38 + (abs(pct) / 4.0))
        candidate_risks.setdefault(asset, [])
        candidate_risks[asset].append(f"{asset} snapshot icinde en zayif momentum tarafinda ({pct:+.2f}%).")


def _freshness_multiplier(ts_value: Any) -> float:
    if not isinstance(ts_value, str) or not ts_value.strip():
        return 1.0
    try:
        ts = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
    except ValueError:
        return 1.0
    age_hours = max(0.0, (datetime.utcnow() - ts.replace(tzinfo=None)).total_seconds() / 3600.0)
    if age_hours <= 8:
        return 1.16
    if age_hours <= 24:
        return 1.08
    if age_hours <= 72:
        return 1.0
    return 0.9


def _assets_in_text(text: str) -> list[str]:
    out: list[str] = []
    for asset, aliases in ASSET_ALIASES.items():
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text) for alias in aliases):
            out.append(asset)
    return out


def _extract_asset_change_signals(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    patterns = (
        r"\b([A-Z]{2,6})\s*:\s*\$?[0-9.,Kk]+\s*\(([+-]?\d+(?:\.\d+)?)%\)",
        r"\b([A-Z]{2,6})\s*:\s*\$?[0-9.,Kk]+\s*([+-]\d+(?:\.\d+)?)%",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            asset = str(match.group(1) or "").strip().upper()
            if asset not in ASSET_ALIASES or asset in seen:
                continue
            try:
                pct = float(str(match.group(2) or "0").replace(",", "."))
            except ValueError:
                continue
            out.append({"asset": asset, "change_pct": pct})
            seen.add(asset)
    return out


def _extract_named_mover(text: str, *, positive: bool) -> dict[str, Any] | None:
    marker = r"en\s+cok\s+yukselen" if positive else r"en\s+cok\s+dusen"
    match = re.search(rf"{marker}\s*:\s*([A-Z]{{2,6}})\s*([+-]?\d+(?:\.\d+)?)%", text, flags=re.IGNORECASE)
    if not match:
        return None
    asset = str(match.group(1) or "").strip().upper()
    if asset not in ASSET_ALIASES:
        return None
    try:
        pct = float(str(match.group(2) or "0").replace(",", "."))
    except ValueError:
        return None
    return {"asset": asset, "change_pct": pct}


def _extract_relative_movers(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for prefix, sign in ((r"yukselenler", 1.0), (r"dusenler", -1.0)):
        match = re.search(rf"{prefix}\s*:\s*([^.;]+)", text, flags=re.IGNORECASE)
        if not match:
            continue
        assets_blob = str(match.group(1) or "")
        for raw_asset in re.split(r"[,|/]", assets_blob):
            asset = raw_asset.strip().upper()
            if asset in ASSET_ALIASES:
                out.append({"asset": asset, "change_pct": 1.4 * sign})
    return out


def _detect_scope(text: str) -> str:
    if any(marker in text for marker in ("hangi coin", "hangi kripto", "hangi token", "altcoin", "kripto")):
        return "crypto"
    if any(marker in text for marker in ("hangi hisse", "hisse", "stock", "equity", "borsa")):
        return "equity"
    return "all"


def _asset_in_scope(asset: str, scope: str) -> bool:
    if scope == "crypto":
        return asset in CRYPTO_ASSETS
    if scope == "equity":
        return asset in EQUITY_ASSETS
    return True


def _is_market_decision_query(text: str) -> bool:
    markers = (
        "hangi coin",
        "hangi kripto",
        "hangi token",
        "almaliyim",
        "almam lazim",
        "en mantikli",
        "kisa vade",
        "kisa vadede",
        "1 ay",
        "2 ay",
        "bir ay",
        "iki ay",
        "short term",
        "hangi hisse",
    )
    return any(marker in text for marker in markers)


def _normalize(text: str) -> str:
    out = (text or "").strip().lower()
    repl = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
    }
    for src, dst in repl.items():
        out = out.replace(src, dst)
    return " ".join(out.split())
