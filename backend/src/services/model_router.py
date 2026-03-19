from __future__ import annotations


def select_model(user_input: str, intent: str) -> dict:
    text = (user_input or "").strip()
    intent_norm = (intent or "").strip().lower()
    tokens = [t for t in text.split() if t.strip()]
    lower = text.lower()

    deep_keys = ("analiz", "karşılaştır", "karsilastir", "rapor", "strateji", "yatırım", "yatirim", "detaylı", "detayli")
    if any(k in lower for k in deep_keys) or intent_norm == "agent_task":
        return {
            "model": "deepseek-chat",
            "mode": "analysis",
            "reason": "deep_analysis_keywords_or_agent_task",
        }

    simple_keys = ("nedir", "kısa", "kisa", "tanım", "tanim")
    if len(tokens) < 20 and any(k in lower for k in simple_keys):
        return {
            "model": "gpt-4o-mini",
            "mode": "fast",
            "reason": "short_with_simple_keywords",
        }

    return {
        "model": "gpt-4o",
        "mode": "chat",
        "reason": "default_assistant_conversation",
    }
