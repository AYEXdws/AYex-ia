from __future__ import annotations

import time

from ayex_core.agent import AyexAgent


def _looks_unclear_transcript(text: str) -> bool:
    n = text.strip()
    if not n:
        return True
    ascii_like = "".join(ch.lower() if ch.isascii() else " " for ch in n)
    tokens = [t for t in ascii_like.split() if t]
    if len(tokens) <= 1:
        return True
    if len(n) <= 3:
        return True
    letters = sum(ch.isalpha() for ch in n)
    if letters <= 2:
        return True
    uniq = {t for t in tokens if len(t) > 1}
    if len(tokens) >= 4 and len(uniq) <= 1:
        return True
    return False


def _voice_state(agent: AyexAgent) -> dict:
    state = getattr(agent, "_voice_state", None)
    if not isinstance(state, dict):
        state = {
            "clarify_streak": 0,
            "last_clarify_ts": 0.0,
        }
        setattr(agent, "_voice_state", state)
    return state


def _reset_clarify_state(agent: AyexAgent) -> None:
    state = _voice_state(agent)
    state["clarify_streak"] = 0
    state["last_clarify_ts"] = 0.0


def _clarify_reply(agent: AyexAgent, reason: str) -> str:
    state = _voice_state(agent)
    now = time.time()
    last_ts = float(state.get("last_clarify_ts", 0.0) or 0.0)
    recent = (now - last_ts) <= 12.0
    streak = int(state.get("clarify_streak", 0) or 0)
    streak = (streak + 1) if recent else 1
    state["clarify_streak"] = streak
    state["last_clarify_ts"] = now

    if streak == 1:
        if reason == "unclear":
            return "Ahmet, seni net duyamadim. Son cumleyi biraz daha yavas tekrar eder misin?"
        return "Ahmet, ne demek istedigini tam yakalayamadim. Tek cumleyle tekrar eder misin?"
    if streak == 2:
        return "Ahmet, mikrofonu biraz yaklastirip tek ve kisa bir cumleyle soyle."
    return "Ahmet, hazir olunca tek cumleyle devam edelim."


class VoiceResponseService:
    """Compatibility-preserving voice reply logic extracted from legacy server."""

    def generate_reply(self, agent: AyexAgent, transcript: str) -> str:
        text = transcript.strip()
        if not text:
            return ""
        if _looks_unclear_transcript(text):
            return _clarify_reply(agent, "unclear")

        profile_capture = agent._capture_profile_facts(text)
        if profile_capture:
            _reset_clarify_state(agent)
            return profile_capture

        intent = agent._rule_intent(text)
        word_len = len(agent._normalized_ascii(text).split())
        if agent._should_try_quick_reply(text, intent) and word_len <= 8:
            quick = agent._quick_reply(text, repeat_count=agent._repeat_count(text))
            if quick:
                _reset_clarify_state(agent)
                return quick if quick.lower().startswith("ahmet") else f"Ahmet, {quick}"

        retrieval = agent.memory.retrieve(text, limit=3)
        recent_items = list(agent.history)[-3:]
        recent_lines = []
        for item in recent_items:
            recent_lines.append(f"Kullanici: {item.get('user', '')}")
            recent_lines.append(f"AYEX: {item.get('assistant', '')}")

        compact = []
        if retrieval:
            compact.append("Ilgili bellek:\n" + "\n".join(f"- {row}" for row in retrieval[:2]))
        if recent_lines:
            compact.append("Son konusma:\n" + "\n".join(recent_lines))

        prompt = (
            f"{chr(10).join(compact)}\n\n"
            f"Kullanici: {text}\n\n"
            "Kurallar:\n"
            "- Kullaniciyi net anlamadiysan uydurma yapma; tek cumleyle tekrar iste.\n"
            "- En fazla 2 cumle, en fazla 24 kelime.\n"
            "- Kisa, net, dogal Turkce.\n"
            "- Sesli asistanda kolay anlasilacak kadar sade yaz.\n"
            "- Gereksiz tekrar ve konu disina cikma.\n"
        )
        reply = agent._chat_llm_response(
            prompt=prompt,
            system=agent._chat_system(),
            temperature=0.12,
            max_tokens=80,
            allow_thinking=False,
        )
        reply = agent._normalize_reply(reply, user_text=text)
        reply = agent._limit_words(reply, 24)
        if intent in {"general", "strategy"} and agent._token_overlap_score(text, reply) < 0.06:
            return _clarify_reply(agent, "off_topic")
        _reset_clarify_state(agent)
        if not reply.lower().startswith("ahmet"):
            reply = f"Ahmet, {reply}"
        return reply
