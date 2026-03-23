from __future__ import annotations

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
}

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

    candidate_scores: dict[str, float] = {}
    candidate_reasons: dict[str, list[str]] = {}
    candidate_risks: dict[str, list[str]] = {}
    candidate_evidence: dict[str, list[str]] = {}

    explicit_assets = _assets_in_text(normalized)
    if explicit_assets:
        for asset in explicit_assets:
            candidate_scores.setdefault(asset, 0.2)

    key_events = list((intel_context or {}).get("key_events") or [])
    for item in key_events:
        _score_event(
            item,
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
            candidate_scores=candidate_scores,
            candidate_reasons=candidate_reasons,
            candidate_risks=candidate_risks,
            candidate_evidence=candidate_evidence,
        )

    if not candidate_scores:
        return MarketDecision(
            active=True,
            stance="wait",
            summary="Net edge yok. Elimde karar verecek kadar guclu market kaniti birikmemis durumda.",
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
            summary=f"Su an tek bir coin'i zorla one cikarmak dogru degil. {top_asset} hafif onde ama edge yeterince temiz degil.",
            reasons=top_reasons or (f"{top_asset} digerlerine gore hafif daha iyi gozukuyor.",),
            risks=top_risks or ("Momentumun kirilgan olma ihtimali var.",),
            evidence=top_evidence,
        )

    stance = "buy" if top_score >= 1.55 else "watch"
    action_phrase = "en mantikli secenek" if stance == "buy" else "izlemeye en deger secenek"
    summary = f"Su an {action_phrase} {top_asset}. Kanit diger adaylardan daha temiz ve daha taze duruyor."
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


def _score_event(
    item: dict[str, Any],
    *,
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
        if any(alias in text for alias in aliases):
            out.append(asset)
    return out


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
