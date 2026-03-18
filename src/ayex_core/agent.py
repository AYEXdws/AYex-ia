from pathlib import Path
import json
import os
import re
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional
from urllib import error as urlerror

from .config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_CHAT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PLAN_MAX_TOKENS,
    DEFAULT_REASONING_MODEL,
    DEFAULT_SUMMARY_MAX_TOKENS,
    MAX_CHAT_WORDS,
    QUALITY_MIN_SCORE,
    Settings,
)
from .memory import MemoryStore
from .openai_client import OpenAIClient
from .system import confirm_input
from .tools import ToolManager


class AyexAgent:
    def __init__(self, workspace: Optional[Path] = None, model: str = DEFAULT_MODEL):
        root = (workspace or Path.cwd()).resolve()
        self.settings = Settings.from_workspace(root)
        self.memory = MemoryStore(self.settings)
        self.tools = ToolManager(self.settings, self.memory, confirm_fn=confirm_input)
        self.llm = OpenAIClient(model=model)
        self.reason_model = os.environ.get("AYEX_REASONING_MODEL", DEFAULT_REASONING_MODEL)
        self.reason_llm = self.llm if self.reason_model == model else OpenAIClient(model=self.reason_model)
        self.mode = "dengeli"
        self.chat_model = os.environ.get("AYEX_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        self.chat_llm = self.llm if self.chat_model == model else OpenAIClient(model=self.chat_model)
        self.chat_max_tokens = DEFAULT_CHAT_MAX_TOKENS
        self.history: Deque[Dict[str, str]] = deque(maxlen=24)
        self.summary_text = ""
        self.turn_counter = 0
        self.strict_framework = False
        self._intent_source = "rule"
        self.last_metrics: Dict[str, Any] = {
            "latency_ms": 0,
            "quality_score": None,
            "intent": "general",
            "intent_source": "rule",
            "mode": self.mode,
            "used_deep_reasoning": False,
            "used_hidden_plan": False,
            "used_consistency_check": False,
            "used_quality_gate": False,
            "used_quick_reply": False,
            "chat_model": self.chat_model,
            "reasoning_model": self.reason_model,
            "chat_model_used": self.chat_model,
            "reasoning_model_used": self.reason_model,
            "coding_model_used": self.llm.model,
        }
        self._run_state: Dict[str, Any] = {}
        self._model_clients: Dict[str, OpenAIClient] = {
            self.llm.model: self.llm,
            self.chat_model: self.chat_llm,
            self.reason_model: self.reason_llm,
        }
        self._model_unhealthy_until: Dict[str, float] = {}
        self._model_cooldown_sec = int(os.environ.get("AYEX_MODEL_COOLDOWN_SEC", "90"))
        self.chat_fallbacks = self._parse_fallback_models("AYEX_CHAT_FALLBACKS", self.chat_model)
        self.reason_fallbacks = self._parse_fallback_models("AYEX_REASON_FALLBACKS", self.reason_model)
        self.coding_fallbacks = self._parse_fallback_models("AYEX_CODING_FALLBACKS", self.llm.model)

    def _set_mode(self, mode: str) -> str:
        modes = {
            "hizli": ("gpt-4.1-mini", 120),
            "ultra_hizli": ("gpt-4.1-mini", 84),
            "dengeli": (DEFAULT_CHAT_MODEL, DEFAULT_CHAT_MAX_TOKENS),
            "derin": (DEFAULT_MODEL, 260),
            "sohbet": ("gpt-4.1-mini", 100),
        }
        if mode not in modes:
            return "Ahmet, gecersiz mod. Kullan: /mode ultra_hizli | hizli | dengeli | derin | sohbet"
        self.mode = mode
        self.chat_model, self.chat_max_tokens = modes[mode]
        self.chat_llm = self.llm if self.chat_model == self.llm.model else OpenAIClient(model=self.chat_model)
        self._model_clients[self.chat_model] = self.chat_llm
        self.chat_fallbacks = self._parse_fallback_models("AYEX_CHAT_FALLBACKS", self.chat_model)
        return f"Ahmet, mod `{mode}` olarak ayarlandi. Sohbet modeli: {self.chat_model}."

    def _parse_fallback_models(self, env_name: str, primary: str) -> List[str]:
        raw = os.environ.get(env_name, "")
        parsed = [x.strip() for x in raw.split(",") if x.strip()]
        models: List[str] = [primary]
        models.extend(parsed)
        dedup: List[str] = []
        for m in models:
            if m not in dedup:
                dedup.append(m)
        return dedup

    def _get_client_for_model(self, model: str) -> OpenAIClient:
        if model not in self._model_clients:
            self._model_clients[model] = OpenAIClient(model=model)
        return self._model_clients[model]

    def _is_model_healthy(self, model: str) -> bool:
        until = self._model_unhealthy_until.get(model, 0.0)
        return time.time() >= until

    def _unhealthy_models_snapshot(self) -> str:
        now = time.time()
        items: List[str] = []
        for model, until in self._model_unhealthy_until.items():
            if until > now:
                remain = int(until - now)
                items.append(f"{model}:{remain}s")
        return ", ".join(items) if items else "yok"

    def _mark_model_unhealthy(self, model: str) -> None:
        self._model_unhealthy_until[model] = time.time() + self._model_cooldown_sec

    def _run_with_fallback(
        self,
        role: str,
        chain: List[str],
        prompt: str,
        system: str,
        temperature: float,
        max_tokens: int,
        allow_thinking: bool,
    ) -> str:
        errors: List[str] = []
        for model in chain:
            if not self._is_model_healthy(model):
                continue
            client = self._get_client_for_model(model)
            try:
                out = client.generate(
                    prompt=prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    allow_thinking=allow_thinking,
                )
                if role == "chat":
                    self._run_state["chat_model_used"] = model
                elif role == "reasoning":
                    self._run_state["reasoning_model_used"] = model
                elif role == "coding":
                    self._run_state["coding_model_used"] = model
                return out
            except Exception as e:
                self._mark_model_unhealthy(model)
                errors.append(f"{model}: {e}")
        raise TimeoutError(f"Tum {role} modelleri basarisiz: {' | '.join(errors)[:500]}")

    def _dedupe_models(self, models: List[str]) -> List[str]:
        out: List[str] = []
        for m in models:
            if m and m not in out:
                out.append(m)
        return out

    def _select_chat_chain(self, max_tokens: int) -> List[str]:
        intent = str(self._run_state.get("intent", "general"))
        user_text = str(self._run_state.get("user_text", "") or "")
        token_len = len(self._normalized_ascii(user_text).split())
        if intent in {"smalltalk", "followup"} or token_len <= 6 or max_tokens <= 120:
            preferred = DEFAULT_CHAT_MODEL
        elif intent == "strategy" or token_len >= 14:
            preferred = self.reason_model
        else:
            preferred = self.chat_model
        return self._dedupe_models([preferred] + self.chat_fallbacks + [self.reason_model])

    def _begin_run(self, intent: str, user_text: str = "") -> None:
        self._run_state = {
            "quality_score": None,
            "intent": intent,
            "intent_source": self._intent_source,
            "user_text": user_text,
            "mode": self.mode,
            "used_deep_reasoning": False,
            "used_hidden_plan": False,
            "used_consistency_check": False,
            "used_quality_gate": False,
            "used_quick_reply": False,
            "chat_model": self.chat_model,
            "reasoning_model": self.reason_model,
            "chat_model_used": self.chat_model,
            "reasoning_model_used": self.reason_model,
            "coding_model_used": self.llm.model,
        }

    def _finish_run(self, latency_ms: int) -> None:
        merged = dict(self._run_state) if self._run_state else {}
        merged["latency_ms"] = latency_ms
        merged["mode"] = self.mode
        merged["chat_model"] = self.chat_model
        merged["reasoning_model"] = self.reason_model
        self.last_metrics = merged

    def get_last_metrics(self) -> Dict[str, Any]:
        return dict(self.last_metrics)

    def _normalized_ascii(self, text: str) -> str:
        out = text.lower()
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
        out = re.sub(r"[^a-z0-9\s]", " ", out)
        return re.sub(r"\s+", " ", out).strip()

    def _repeat_count(self, text: str) -> int:
        key = self._normalized_ascii(text)
        key_tokens = set(key.split())
        cnt = 0
        for item in reversed(self.history):
            old_key = item["user_key"]
            if old_key == key:
                cnt += 1
                continue
            old_tokens = set(old_key.split())
            if key_tokens and old_tokens:
                inter = len(key_tokens & old_tokens)
                union = len(key_tokens | old_tokens)
                sim = inter / union if union else 0.0
                if sim >= 0.72:
                    cnt += 1
        return cnt

    def _render_recent_history(self, n: int = 6) -> str:
        if not self.history:
            return "(yok)"
        items = list(self.history)[-n:]
        lines = []
        for t in items:
            lines.append(f"Kullanici: {t['user']}")
            lines.append(f"AYEX: {t['assistant']}")
        return "\n".join(lines)

    def _record_turn(self, user_text: str, assistant_text: str, intent: str = "general") -> None:
        self.history.append(
            {
                "user_key": self._normalized_ascii(user_text),
                "user": user_text,
                "assistant": assistant_text,
                "intent": intent,
            }
        )
        self.turn_counter += 1
        self._learn_from_turn(user_text, assistant_text)
        if intent in {"strategy", "general"}:
            self._maybe_refresh_summary()
        self._maybe_store_episode()

    def _learn_from_turn(self, user_text: str, assistant_text: str) -> None:
        n = self._normalized_ascii(user_text)
        if any(k in n for k in {"alakasiz", "yetersiz", "tekrar", "yanlis", "sacma"}):
            self.strict_framework = False
            self.memory.append_memory(
                text=f"Kalite geri bildirimi: {user_text}",
                kind="feedback",
                tags=["quality", "auto_learn"],
            )
        if "sohbet" in n and any(k in n for k in {"istiyorum", "edelim", "edelim"}):
            self.memory.append_memory(
                text="Kullanici sohbet odakli dogal akisi tercih ediyor.",
                kind="preference",
                tags=["chat_mode", "auto_learn"],
            )

    def _capture_profile_facts(self, text: str) -> Optional[str]:
        low = self._normalized_ascii(text)
        raw_low = text.lower().strip()
        age_match = re.search(r"\b(?:benim yasim|yasim)\s+(\d{1,3})\b", low)
        if age_match:
            age = int(age_match.group(1))
            if 5 <= age <= 120:
                self.memory.update_profile({"age": age})
                return f"Ahmet, yaşını {age} olarak kaydettim."
        interest_match = re.search(r"\bilgi alanlar[ıi]m?\s+(.*)$", raw_low)
        if interest_match:
            raw = interest_match.group(1).strip()
            if raw:
                items = [x.strip() for x in re.split(r"[,;/]", raw) if x.strip()]
                if items:
                    profile = self.memory.load_profile()
                    prev = profile.get("preferences", [])
                    merged = self._clean_preferences(prev + items)
                    self.memory.update_profile({"preferences": merged})
                    return f"Ahmet, ilgi alanlarini kaydettim: {', '.join(items[:6])}."
        goal_match = re.search(r"\bhedefim\s+(.*)$", raw_low)
        if goal_match:
            goal = goal_match.group(1).strip()
            if goal:
                self.memory.update_profile({"goal": goal})
                return f"Ahmet, hedefini kaydettim: {goal}."
        return None

    def _handle_profile_command(self, text: str) -> Optional[str]:
        if not text.startswith("/profil"):
            return None
        cmd = text[len("/profil") :].strip()
        if not cmd or cmd == "goster":
            profile = self.memory.load_profile()
            age = profile.get("age", "kayitli degil")
            goal = profile.get("goal", "kayitli degil")
            loc = profile.get("location", "kayitli degil")
            edu = profile.get("education", "kayitli degil")
            aliases = ", ".join(profile.get("aliases", [])) or "kayitli degil"
            calls = ", ".join(profile.get("preferred_calls", [])) or "kayitli degil"
            prefs_list = self._clean_preferences(profile.get("preferences", []))
            if prefs_list != profile.get("preferences", []):
                self.memory.update_profile({"preferences": prefs_list})
            prefs = ", ".join(prefs_list) or "kayitli degil"
            return (
                "Ahmet, profilin: "
                f"yas={age}, konum={loc}, egitim={edu}, hedef={goal}, "
                f"takma_ad={aliases}, hitap={calls}, ilgi={prefs}"
            )
        if cmd.startswith("yas "):
            val = cmd[4:].strip()
            if not val.isdigit():
                return "Ahmet, yas sayi olmali. Ornek: /profil yas 17"
            age = int(val)
            self.memory.update_profile({"age": age})
            return f"Ahmet, yasini {age} olarak kaydettim."
        if cmd.startswith("hedef "):
            goal = cmd[6:].strip()
            if not goal:
                return "Ahmet, hedef bos olamaz."
            self.memory.update_profile({"goal": goal})
            return f"Ahmet, hedefini kaydettim: {goal}"
        if cmd.startswith("ilgi "):
            parts = [x.strip() for x in cmd[5:].split(",") if x.strip()]
            if not parts:
                return "Ahmet, ilgi listesi bos."
            profile = self.memory.load_profile()
            merged = self._clean_preferences(profile.get("preferences", []) + parts)
            self.memory.update_profile({"preferences": merged})
            return f"Ahmet, ilgi alanlarini guncelledim: {', '.join(parts)}"
        return "Ahmet, profil komutlari: /profil goster | /profil yas <n> | /profil hedef <metin> | /profil ilgi <a,b>"

    def _clean_preferences(self, values: list[str]) -> list[str]:
        def ascii_norm(s: str) -> str:
            repl = {"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}
            out = s
            for a, b in repl.items():
                out = out.replace(a, b)
            return out

        cleaned: list[str] = []
        for v in values:
            item = re.sub(r"\s+", " ", v.strip().lower())
            if item:
                cleaned.append(item)
        unique = sorted(set(cleaned))
        singles = {ascii_norm(x) for x in unique if " " not in x}
        filtered: list[str] = []
        for item in unique:
            words = [ascii_norm(w) for w in item.split()]
            if len(words) >= 3 and all(w in singles for w in words):
                continue
            filtered.append(item)
        return filtered

    def _profile_system_context(self) -> str:
        p = self.memory.load_profile()
        aliases = ", ".join(p.get("aliases", [])) or "yok"
        nicknames = ", ".join(p.get("preferred_calls", [])) or "Ahmet"
        location = p.get("location", "belirtilmedi")
        core = "; ".join(p.get("core_traits", [])) or "analitik ve derinlik odakli"
        axes = "; ".join(p.get("life_axes", [])) or "projeler, egitim, aile sorumluluklari"
        tone = p.get("communication_tone", "olgun, vurucu, agir")
        framework = " > ".join(p.get("work_framework", [])) or "hedef > varsayim > plan > risk > sert elestiri > alternatif"
        return (
            f"Kullanici ozeti: Ahmet ({aliases}), konum={location}. "
            f"Tercih edilen hitaplar: {nicknames}. "
            f"Cekirdek ozellikler: {core}. Ana eksenler: {axes}. "
            f"Iletisim tonu: {tone}. Calisma formati: {framework}."
        )

    def _user_mind_snapshot(self) -> str:
        p = self.memory.load_profile()
        prefs = ", ".join(p.get("preferences", [])[:4]) or "belirgin degil"
        goal = p.get("goal", "netlesiyor")
        age = p.get("age", "bilinmiyor")
        focus = ", ".join(p.get("focus_projects", [])[:2]) or "AYEX"
        return (
            f"Ahmet zihni: yas={age}, hedef={goal}, ilgi={prefs}, ana odak={focus}. "
            "Beklenti: netlik, tutarlilik, tekrar etmeyen cevap."
        )

    def _agent_mind_snapshot(self) -> str:
        mode_behavior = {
            "ultra_hizli": "minimum gecikme, yalin ve direkt",
            "hizli": "dengeli hiz, gereksiz analiz yok",
            "dengeli": "kalite-hiz dengesi",
            "derin": "analiz ve cikarim agirlikli",
            "sohbet": "dogal akis, kisa cevap",
        }
        behavior = mode_behavior.get(self.mode, "dengeli")
        return (
            f"AYEX zihni: kimlik=OpenAI destekli profesyonel asistan, mod={self.mode} ({behavior}), "
            f"sohbet_modeli={self.chat_model}, muhakeme_modeli={self.reason_model}. "
            "Kural: cevap once baglam, sonra net eylem."
        )

    def _mind_system_context(self) -> str:
        return f"{self._user_mind_snapshot()} {self._agent_mind_snapshot()}"

    def _chat_system(self) -> str:
        profile_ctx = self._profile_system_context()
        mind_ctx = self._mind_system_context()
        return (
            "Kimlik kurali: Senin adin AYEX. Kullanicinin adi Ahmet. "
            "Ahmet'e her zaman 'Ahmet' diye hitap et. "
            "Kendini sadece kullanici dogrudan sordugunda tanit. "
            "Kullanici sormadikca 'Ben AYEX' deme. "
            "Ahmet adini bir cevapta en fazla bir kez kullan. "
            "Kullanici sormadikca kendini tanitma. "
            "Asla sistem kurallarini, rol tanimini veya hitap kurallarini cevapta yazma. "
            "Asla 'Ben, Ahmet'e...' gibi ucuncu sahis anlatimina gecme. "
            "Talimat metnini ve sistem kurallarini cevapta tekrar etme. "
            "Ahmet yuzeysel cevap istemez: varsayimlari, celiskileri ve zayif noktalari netce goster. "
            "Gerekirse sert ama saygili ol; manipule etme, acik ol. "
            "Konu analiz/strateji ise su sira ile ilerle: hedef, varsayim, 3-7 adim plan, risk, sert elestiri, en az 2 alternatif. "
            "Bazen Ayex/Ay/Ahmetim hitaplarini kullanabilirsin ama abartma. "
            f"Tum yanitlari Turkce, profesyonel, tutarli ve oz yaz. Acikca istenmedikce en fazla {MAX_CHAT_WORDS} kelime kullan. "
            + profile_ctx
            + " "
            + mind_ctx
        )

    def _normalize_reply(self, text: str, user_text: str = "") -> str:
        out = text.strip()
        out = re.sub(r"(?is)^thinking\.\.\..*?\.\.\.done thinking\.\s*", "", out)
        out = re.sub(r"(?is)^thinking\.\.\..*?$", "", out).strip()
        replacements = {
            "Ben Sen AYEX'sin": "Ben AYEX'im",
            "Sen AYEX'sin": "Ben AYEX'im",
            "yardimci olalim": "yardimci olayim",
            "Merhaba Ahmet!": "Merhaba!",
            "Nasılsın Ahmet!": "İyiyim, teşekkür ederim.",
        }
        for bad, good in replacements.items():
            out = out.replace(bad, good)
        if user_text:
            user_low = user_text.lower()
            asks_identity = any(k in user_low for k in ["kimsin", "adın ne", "adin ne", "who are you"])
            if not asks_identity:
                out = re.sub(r"(?i)\bben ayex(?:im|\'im|ım|\'ım)?[.!]?\s*", "", out).strip()
                out = re.sub(r"(?i)\bayex(?:im|\'im|ım|\'ım)?[.!]?\s*", "", out).strip()
            out = re.sub(r"(?i)ben,\s*ahmet'e her zaman 'ahmet' diye hitap ediyorum\.?\s*", "", out).strip()
            out = re.sub(r"(?i)ahmet'e her zaman 'ahmet' diye hitap ediyorum\.?\s*", "", out).strip()
        out = re.sub(r"(?i)\bahmet,\s*ahmet\b", "Ahmet", out)
        out = re.sub(r"(?i)\b(Ben AYEX\.)\s*\1\b", r"\1", out)
        out = re.sub(r"(?i)\bMerhaba Ahmet\b", "Merhaba", out)
        out = re.sub(r"\s{2,}", " ", out).strip()
        if not out:
            out = "Kisa ve net yardim icin hazirim."
        return out

    def _limit_words(self, text: str, limit: int = MAX_CHAT_WORDS) -> str:
        words = text.split()
        if len(words) <= limit:
            return text
        return " ".join(words[:limit]).rstrip() + "..."

    def _is_low_information_reply(self, reply: str) -> bool:
        cleaned = reply.strip().lower().strip(".! ")
        return cleaned in {
            "hazirim",
            "hazırim",
            "hazırım",
            "kisa ve net yardim icin hazirim",
            "kısa ve net yardım için hazırım",
        }

    def _token_overlap_score(self, a: str, b: str) -> float:
        at = set(self._normalized_ascii(a).split())
        bt = set(self._normalized_ascii(b).split())
        if not at or not bt:
            return 0.0
        inter = len(at & bt)
        union = len(at | bt)
        prefix_match = 0
        for x in at:
            if len(x) < 4:
                continue
            if any(y.startswith(x[:4]) or x.startswith(y[:4]) for y in bt if len(y) >= 4):
                prefix_match += 1
        soft_inter = inter + (0.4 * prefix_match)
        return soft_inter / union if union else 0.0

    def _is_smalltalkish(self, normalized: str, tokens: set[str]) -> bool:
        compact = normalized.replace(" ", "")
        if tokens & {"merhaba", "selam", "sa", "nasilsin", "naber", "tesekkur", "tesekkurler"}:
            return True
        # Typo toleransli "iyiyim" varyasyonlari (iyiyim, iyiyimm, iyiyimmm, iyii vb.)
        if re.match(r"^iyi+y*i*m+$", compact):
            return True
        if compact.startswith("tesek") and len(compact) <= 14:
            return True
        if compact in {"iyiyim", "iyiyimm", "iyiyimmm", "iyii", "iyiyimdir"}:
            return True
        return False

    def _rule_intent(self, text: str) -> str:
        n = self._normalized_ascii(text)
        tokens = set(n.split())
        if self._is_smalltalkish(n, tokens):
            return "smalltalk"
        if any(k in n for k in ["ben kimim", "adim ne", "ismim ne", "kimsin", "yasim kac"]):
            return "identity"
        if any(k in n for k in ["strateji", "plan", "risk", "varsayim", "karar", "tradeoff", "neden", "niye"]):
            return "strategy"
        if len(tokens) <= 8 and any(k in tokens for k in {"bunu", "onu", "buna", "sunu", "detay", "ac", "devam"}):
            return "followup"
        return "general"

    def _llm_intent_hint(self, text: str) -> Optional[str]:
        if self.mode in {"ultra_hizli", "hizli"}:
            return None
        recent = self._render_recent_history(4)
        prompt = (
            "Kullanici mesajini tek etiketle siniflandir.\n"
            "Yalnizca su etiketlerden birini yaz: smalltalk, identity, strategy, followup, general.\n\n"
            f"Mesaj: {text}\n"
            f"Son konusma: {recent}"
        )
        try:
            raw = self._run_with_fallback(
                role="intent",
                chain=self._dedupe_models([DEFAULT_CHAT_MODEL, self.chat_model]),
                prompt=prompt,
                system="Sadece tek etiket dondur.",
                temperature=0.0,
                max_tokens=8,
                allow_thinking=False,
            )
        except Exception:
            return None
        label = self._normalized_ascii(raw).split(" ")[0].strip()
        valid = {"smalltalk", "identity", "strategy", "followup", "general"}
        return label if label in valid else None

    def _detect_intent(self, text: str) -> str:
        rule = self._rule_intent(text)
        tokens = self._normalized_ascii(text).split()
        if rule in {"smalltalk", "identity", "strategy", "followup"}:
            self._intent_source = "rule"
            return rule
        if len(tokens) < 2 or len(tokens) > 24:
            self._intent_source = "rule"
            return rule
        hint = self._llm_intent_hint(text)
        if hint:
            self._intent_source = "hybrid"
            return hint
        self._intent_source = "rule"
        return rule

    def _should_try_quick_reply(self, text: str, intent: str) -> bool:
        n = self._normalized_ascii(text)
        token_len = len(n.split())
        if intent in {"smalltalk", "identity", "followup"}:
            return True
        if token_len <= 4:
            return True
        strong_markers = {
            "mindbloom",
            "ben kimim",
            "nasil uygularim",
            "bu hafta",
            "odaklanmaliyim",
            "neye odak",
            "ne tur seyler ile ilgilenmeliyim",
            "yasim kac",
            "adim ne",
            "kimsin",
        }
        return any(m in n for m in strong_markers)

    def _quick_reply(self, text: str, repeat_count: int = 0) -> Optional[str]:
        low = text.lower().strip()
        normalized = self._normalized_ascii(text)

        tokens = set(normalized.split())
        token_len = len(tokens)

        defer_words = {"sonra", "erteleriz", "beklesin", "simdi", "degil"}
        ack_words = {"tamam", "ok", "peki", "olur", "anladim", "eyvallah", "super"}
        confusion_words = {"anlamadim", "karisik", "karisti", "net", "degil"}
        name_words = {"isim", "adim", "ad", "adi", "ismim"}
        ask_words = {"ne", "nedir", "kim", "hangi", "neydi"}
        positive_smalltalk = {
            "iyiyim",
            "tesekkur",
            "tesekkurler",
            "sag ol",
            "sagol",
            "iyi",
            "fena degil",
            "super",
            "harika",
        }
        compact = normalized.replace(" ", "")

        # Niyet: erteleme / sonra yapma
        if ("sonra" in tokens or "erteleriz" in tokens or "beklesin" in tokens) and (
            "olur" in tokens or "mu" in tokens or "mi" in tokens or "yapariz" in normalized or "yapalim" in normalized
        ):
            return "Ahmet, olur. O zaman bunu beklemeye alalim; hazir oldugunda 15 dakikalik hizli planla devam ederiz."

        # Niyet: onay / tamamlama
        if tokens & ack_words and token_len <= 7:
            return "Ahmet, net. Hazirsan bir sonraki adimi tek tek kuralim."

        # Niyet: gundelik olumlu sohbet
        if (
            self._is_smalltalkish(normalized, tokens)
            and token_len <= 3
            and normalized not in {"nasilsin", "naber", "ne haber", "merhaba", "selam", "hey", "sa"}
        ):
            return (
                "Ahmet, harika. Istersen bugun icin tek net hedef secip hemen baslayalim."
                if repeat_count == 0
                else "Ahmet, super. Hazirsan bir sonraki konuya gecelim."
            )
        if (tokens & positive_smalltalk) and token_len <= 8:
            return (
                "Ahmet, harika. Istersen bugun icin tek net hedef secip hemen baslayalim."
                if repeat_count == 0
                else "Ahmet, super. Hazirsan bir sonraki konuya gecelim."
            )

        # Niyet: anlamadim / net degil
        if "anlamad" in normalized or (
            tokens & confusion_words and ("degil" in tokens or "karisik" in tokens or "karisti" in tokens)
        ):
            return "Ahmet, daha net anlatayim: once hedefi tek cumlede yaz, sonra 3 adimlik mini plani birlikte cikaralim."
        if any(k in normalized for k in ["biraz daha ac", "acabilir misin", "detaylandir", "daha detay"]):
            return (
                "Ahmet, tabii. Bir onceki cevabin hangi kismini acmami istersin: hedef, adimlar, riskler veya alternatifler?"
            )

        # Niyet: isim/ad sorgusu
        if (tokens & name_words) and (tokens & ask_words or "?" in low or token_len <= 4):
            return "Ahmet, ismin Ahmet."
        if "ben kimim" in normalized:
            p = self.memory.load_profile()
            core = ", ".join(p.get("core_traits", [])[:5]) or "analitik ve derinlik odakli"
            goal = p.get("goal", "sistem kurup gelistirmek")
            if repeat_count >= 1:
                return (
                    f"Ahmet, bir ust cevabimi netlestireyim: kimliginin omurgasi `yeniden insa + netlik`. "
                    f"Stratejik eksenin `{goal}`; guclu yanin ise gozlem ve analitik disiplin."
                )
            return (
                f"Ahmet, sen gozlemci ve derinlik arayan bir insansin; "
                f"kendini yeniden insa etme motivasyonun yuksek. Karar aninda netlik ariyor, "
                f"su an ana hedef olarak `{goal}` cizgisinde ilerliyorsun. "
                f"Cekirdek karakterin: {core}."
            )
        if normalized in {"merhaba", "selam", "hey", "sa"}:
            return "Ahmet, merhaba." if repeat_count == 0 else "Ahmet, buradayim. Devam edelim."
        if normalized in {"nasilsin", "naber", "ne haber"}:
            return (
                "Ahmet, iyiyim, teşekkür ederim. Sen nasılsın?"
                if repeat_count == 0
                else "Ahmet, iyi durumdayim. Istersen direkt gundemine gecelim."
            )
        if "mindbloom" in normalized and ("zayif" in normalized or "elestiri" in normalized):
            return (
                "Ahmet, sert gerçek: MindBloom'un en zayıf noktası 'çok geniş vaat, düşük ölçülebilirlik'. "
                "Eğer net çıktı metriği yoksa ürün koçluk söylemine sıkışır. "
                "Alternatif-1: Tek niş (ör. sınav stresi) + 30 günlük ölçülebilir protokol. "
                "Alternatif-2: B2C yerine okul/kurum odaklı B2B pilot, net sonuç raporu ile satış."
            )
        if "mindbloom" in normalized and ("varsayim" in normalized or "risk" in normalized):
            return (
                "Ahmet, en riskli 3 varsayım: 1) Kullanıcı 30 gün düzenli kullanır, 2) AI önerileri klinik olarak anlamlı fayda üretir, "
                "3) Etik/sunum dili güven yaratır. Test planı: her varsayımı 2 haftalık pilotla ölç. "
                "Metrikler: D7-D30 tutunma, öznel iyi oluş skoru değişimi, öneri kabul oranı, terk nedeni. "
                "Sert gerçek: metrik yoksa MindBloom fikir olarak iyi, ürün olarak kırılgan kalır."
            )
        if "ne tur seyler ile ilgilenmeliyim" in normalized:
            profile = self.memory.load_profile()
            age = profile.get("age")
            goal = profile.get("goal")
            prefs = profile.get("preferences", [])
            if age:
                if repeat_count >= 1:
                    return (
                        f"Ahmet, tekrar etmeyeyim; bu kez direkt haftalik isleyis: "
                        "Pzt-Crs-Cum 90 dk yazilim + 30 dk Ingilizce, "
                        "Sali-Persembe 45 dk spor + 45 dk proje notlari, "
                        f"Hafta sonu 2 saat `{goal or 'ana hedefin'}` icin prototip."
                    )
                base = f"Ahmet, {age} yas icin odak: yazilim temelleri, Ingilizce, duzenli spor ve bir proje portfoyu."
                if goal:
                    base += f" Ana hedefin `{goal}` icin haftalik 3 saat blok ayir."
                if prefs:
                    base += f" Ilgilerine gore baslangic listesi: {', '.join(prefs[:3])}."
                return base
            return (
                "Ahmet, teknoloji-yazılım, İngilizce, iletişim becerisi ve düzenli spor iyi bir temel olur. "
                "Bir alan seçip 90 gün boyunca tek projeye odaklan."
            )
        if "nasil uygularim" in normalized or "bunu nasil uygularim" in normalized:
            profile = self.memory.load_profile()
            goal = profile.get("goal", "ana hedefin")
            return (
                f"Ahmet, uygulama plani: 1) Bugun 30 dk hedef parcala (`{goal}` -> ilk mini gorev). "
                "2) Yarindan itibaren 7 gun, her gun 90 dk tek blok calis. "
                "3) Her blok sonunda 3 satir ilerleme notu yaz. "
                "4) 7. gun ciktiyi olc, ise yaramayani acimasizca kes."
            )
        if "bu hafta" in normalized and ("odagim" in normalized or "hedefim" in normalized):
            profile = self.memory.load_profile()
            goal = profile.get("goal", "ana hedefin")
            return (
                f"Ahmet, bu hafta tek odak `{goal}` olsun. "
                "Plan: her gun 90 dk tek blok, hafta sonunda somut bir cikti ve kisa degerlendirme."
            )
        if "odaklanmaliyim" in normalized or "neye odak" in normalized:
            profile = self.memory.load_profile()
            goal = profile.get("goal", "ana hedefin")
            return (
                f"Ahmet, bugun odagin `{goal}` olsun. "
                "Ilk 90 dakikayi tek goreve ver; bitiste 3 satir ilerleme notu cikar."
            )
        user_age_patterns = [
            r"\bbenim yasim\b",
            r"\byasim kac\b",
            r"\byaşim kac\b",
            r"\byaşım kaç\b",
            r"\bkac yasindayim\b",
            r"\bkaç yaşındayım\b",
            r"\bben kac yasindayim\b",
            r"\bben kaç yaşındayım\b",
        ]
        if any(re.search(p, normalized) for p in user_age_patterns):
            profile = self.memory.load_profile()
            age = profile.get("age")
            if age:
                return f"Ahmet, kayıtlı yaşın {age}."
            return "Ahmet, yaş bilgin kayıtlı değil. İstersen profile ekleyebilirim."
        if normalized in {"kimsin", "adin ne", "sen kimsin"}:
            return "Ahmet, ben AYEX."
        return None

    def _framework_fallback(self, text: str) -> str:
        n = self._normalized_ascii(text)
        tokens = set(n.split())
        casual_words = {"iyiyim", "tesekkur", "tesekkurler", "sagol", "merhaba", "tamam", "ok"}
        if tokens & casual_words and len(tokens) <= 8:
            return "Ahmet, anladim. Istersen burada kisa sohbet ederiz, istersen direkt bir hedefe geceriz."
        if any(k in n for k in ["sonra", "herneyse", "her neyse", "bosver", "simdi degil"]):
            return "Ahmet, olur. O zaman bunu beklemeye alalim; hazir oldugunda 15 dakikalik hizli planla devam ederiz."
        if "yks" in n and "aile" in n and "proje" in n:
            return (
                "Ahmet, karar mekanizmasi: 1) Hedef: YKS birinci oncelik, aile isi ikinci, proje ucuncu. "
                "2) Varsayim: haftada 45 saat efektif zamanin var. 3) Plan: 30s YKS, 10s aile isi, 5s proje. "
                "4) Risk: aile isi tasarsa YKS zarar gorur; bunu gunluk 2 saat siniri ile kilitle. "
                "5) Sert elestiri: takvim degil disiplin belirleyici; her gun cikti yazmazsan sistem cop. "
                "6) Alternatifler: A) 6 gun calis/1 gun toparla, B) 5 gun yogun/2 gun esnek model."
            )
        if any(k in n for k in ["strateji", "plan", "risk", "karar", "varsayim"]):
            return (
                "Ahmet, net cizgi: once hedefi tek cumlede kilitle, sonra 3 varsayim yaz ve her varsayimi 7 gunde test et. "
                "Ardindan 3 adimli plan kur (baslangic, olcum, duzeltme). En buyuk riskleri once sirala ve her riske bir erken alarm tanimla. "
                "Sert gercek: olculemeyen fikir sadece iyi hissettirir, sonuc uretmez. "
                "Iki yol: hizli pilot (dusuk maliyet, hizli veri) veya kontrollu pilot (az kullanici, derin kalite)."
            )
        return "Ahmet, mesajini aldim. Net cevap verebilmem icin bunu tek cumle daha ac: neyi, ne kadar surede basarmak istiyorsun?"

    def _contextual_timeout_reply(self, text: str, intent: str) -> str:
        quick = self._quick_reply(text, repeat_count=self._repeat_count(text))
        if quick:
            return quick
        n = self._normalized_ascii(text)
        tokens = [t for t in n.split() if len(t) > 2]
        if intent == "smalltalk":
            return "Ahmet, seni duyuyorum. Kisa sohbete devam edebiliriz; ben hazirim."
        if any(k in n for k in ["strateji", "plan", "risk", "hedef", "karar"]):
            return (
                "Ahmet, model gecikiyor; hizli cerceve: hedefi tek cumle yaz, "
                "3 adim sec, en buyuk riski ilk adimda kilitleyelim."
            )
        if any(k in n for k in ["yks", "aile", "proje"]):
            return (
                "Ahmet, model gecikiyor; kisa odak: YKS birinci, aile isi ikinci, proje ucuncu. "
                "Istersen bunu haftalik saat planina cevireyim."
            )
        if tokens:
            key = ", ".join(tokens[:3])
            return (
                f"Ahmet, model gecikiyor; ama mesaji aldim: `{key}` odaginda devam edelim. "
                "Istersen buna 3 adimli net plan cikarayim."
            )
        return "Ahmet, model gecikiyor. Tek cumlelik hedefini yaz; aninda net bir plan vereyim."

    def _is_coding_task(self, text: str) -> bool:
        low = text.lower()
        phrase_keys = {"write code", "add tests"}
        if any(p in low for p in phrase_keys):
            return True
        word_keys = {
            "fix",
            "bug",
            "implement",
            "feature",
            "refactor",
            "patch",
            "diff",
            "repository",
            "codebase",
        }
        words = set(re.findall(r"[a-z0-9_]+", low))
        return any(k in words for k in word_keys)

    def _render_retrieval(self, query: str) -> str:
        snippets = self.memory.retrieve(query=query, limit=6)
        recent_scored: List[tuple[float, str]] = []
        for item in list(self.history)[-8:]:
            user_line = f"recent.user: {item.get('user', '')}"
            assistant_line = f"recent.ayex: {item.get('assistant', '')}"
            user_score = self._token_overlap_score(query, user_line)
            assistant_score = self._token_overlap_score(query, assistant_line)
            score = max(user_score, assistant_score * 0.7)
            if score >= 0.08:
                recent_scored.append((score, user_line))
                recent_scored.append((score * 0.8, assistant_line))
        recent_scored.sort(key=lambda x: x[0], reverse=True)
        recent_lines: List[str] = []
        seen_recent = set()
        for _, line in recent_scored:
            if line not in seen_recent:
                seen_recent.add(line)
                recent_lines.append(line)
            if len(recent_lines) >= 4:
                break
        merged = recent_lines + snippets
        return "\n".join(f"- {s}" for s in merged)

    def _coding_llm(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = DEFAULT_CHAT_MAX_TOKENS,
        allow_thinking: bool = False,
    ) -> str:
        chain = self.coding_fallbacks
        return self._run_with_fallback(
            role="coding",
            chain=chain,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            allow_thinking=allow_thinking,
        )

    def _chat_llm_response(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = DEFAULT_CHAT_MAX_TOKENS,
        allow_thinking: bool = False,
    ) -> str:
        chain = self._select_chat_chain(max_tokens)
        return self._run_with_fallback(
            role="chat",
            chain=chain,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            allow_thinking=allow_thinking,
        )

    def _reason_llm_response(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 220,
        allow_thinking: bool = True,
    ) -> str:
        chain = list(self.reason_fallbacks)
        return self._run_with_fallback(
            role="reasoning",
            chain=chain,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            allow_thinking=allow_thinking,
        )

    def _extract_json(self, text: str) -> Dict[str, object]:
        block = text.strip()
        m = re.search(r"(?s)\{.*\}", block)
        if m:
            block = m.group(0)
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {}

    def _maybe_refresh_summary(self) -> None:
        if self.mode == "ultra_hizli":
            return
        if len(self.history) < 2:
            return
        if self.turn_counter % 3 != 0:
            return
        recent = self._render_recent_history(8)
        prompt = (
            "Aşağıdaki konuşmayı kısa bağlam özetine dönüştür.\n"
            "Kurallar: 6 maddeyi geçme, kullanıcı hedefi/kararları/açık konuları yaz, tekrar etme.\n\n"
            f"Mevcut özet:\n{self.summary_text or '(yok)'}\n\n"
            f"Yeni konuşma:\n{recent}"
        )
        summary = self._reason_llm_response(
            prompt=prompt,
            system="Sadece Türkçe kısa özet üret.",
            temperature=0.1,
            max_tokens=180,
            allow_thinking=False,
        )
        summary = self._normalize_reply(summary)
        if summary and not self._is_low_information_reply(summary):
            self.summary_text = summary

    def _maybe_store_episode(self) -> None:
        if len(self.history) < 6:
            return
        if self.turn_counter % 6 != 0:
            return
        window = list(self.history)[-10:]
        non_smalltalk = [x for x in window if x.get("intent") not in {"smalltalk"}]
        base = non_smalltalk if non_smalltalk else window
        if not base:
            return
        last_user = base[-1].get("user", "").strip()
        topic_seed = self._normalized_ascii(last_user)
        topic_words = topic_seed.split()
        topic = " ".join(topic_words[:6]).strip() or f"turn-{self.turn_counter}"
        facts: List[str] = []
        for item in base[-4:]:
            u = item.get("user", "").strip()
            if u:
                facts.append(f"kullanici: {u[:120]}")
        summary = (
            f"Son {len(base)} mesajda ana odak `{topic}`. "
            f"Kullanici niyeti agirlikli olarak `{base[-1].get('intent', 'general')}`. "
            "Cevaplar bu odağı koruyacak şekilde sürdürülmeli."
        )
        self.memory.append_episode(topic=topic, summary=summary, facts=facts[:4])

    def _evaluate_quality(self, user_text: str, reply: str, retrieval: str, recent: str) -> Dict[str, object]:
        heur_score = 85
        user_norm = self._normalized_ascii(user_text)
        reply_norm = self._normalized_ascii(reply)
        overlap = self._token_overlap_score(user_text, reply)
        if self._is_low_information_reply(reply):
            heur_score = 30
        if len(reply.strip()) < 25 and len(user_text.split()) > 4:
            heur_score = min(heur_score, 45)
        if reply.count("Ahmet") > 2:
            heur_score = min(heur_score, 55)
        if len(user_text.split()) >= 4 and overlap < 0.08:
            heur_score = min(heur_score, 35)
        if "yas" in reply_norm and "yas" not in user_norm:
            heur_score = min(heur_score, 25)
        # Hizli kalite kontrolu: kisa/gundelik cevaplarda LLM denetimi yerine deterministik skor.
        if len(user_text.split()) <= 5 and len(reply.split()) <= 20:
            self._run_state["quality_score"] = heur_score
            return {"score": heur_score, "issues": [], "hint": ""}

        prompt = (
            "Asagidaki cevabi kalite acisindan puanla.\n"
            "JSON disinda hicbir sey dondurme.\n"
            'Format: {"score": 0-100, "issues": ["..."], "rewrite_hint": "..."}\n'
            f"Kullanici: {user_text}\n"
            f"Cevap: {reply}\n"
            f"Bellek: {retrieval[:800]}\n"
            f"Konusma ozeti: {recent[:800]}"
        )
        raw = self._reason_llm_response(
            prompt=prompt,
            system="Kalite denetleyici gibi davran.",
            temperature=0.0,
            max_tokens=140,
            allow_thinking=False,
        )
        data = self._extract_json(raw)
        score = data.get("score", heur_score)
        try:
            score_val = int(score)
        except Exception:
            score_val = heur_score
        score_val = max(0, min(100, score_val))
        if abs(score_val - heur_score) > 45:
            score_val = heur_score
        issues = data.get("issues", [])
        hint = data.get("rewrite_hint", "")
        if not isinstance(issues, list):
            issues = []
        if not isinstance(hint, str):
            hint = ""
        self._run_state["quality_score"] = score_val
        return {"score": score_val, "issues": issues, "hint": hint}

    def _rewrite_with_quality_gate(self, user_text: str, reply: str, retrieval: str, recent: str) -> str:
        if self.mode == "ultra_hizli":
            self._run_state["quality_score"] = 78 if not self._is_low_information_reply(reply) else 40
            return reply
        self._run_state["used_quality_gate"] = True
        review = self._evaluate_quality(user_text, reply, retrieval, recent)
        score = int(review.get("score", 0))
        if score >= QUALITY_MIN_SCORE and not self._is_low_information_reply(reply):
            return reply
        hint = review.get("hint", "")
        rewrite_prompt = (
            "Cevabi iyilestir. Ayni anlama sadik kal ama daha net, baglama uygun, tutarli yap.\n"
            "Kurallar: 4-7 cumle, tekrar yok, genel laf yok, uygulanabilir netlik.\n"
            f"Kullanici mesaji: {user_text}\n"
            f"Zayif cevap: {reply}\n"
            f"Iyilestirme ipucu: {hint}\n"
            f"Bellek: {retrieval[:1200]}\n"
            f"Konusma ozeti: {recent[:1200]}"
        )
        better = self._reason_llm_response(
            prompt=rewrite_prompt,
            system=self._chat_system(),
            temperature=0.12,
            max_tokens=220,
            allow_thinking=False,
        )
        better = self._normalize_reply(better, user_text=user_text)
        candidate = better if better and not self._is_low_information_reply(better) else reply
        if self._is_low_information_reply(candidate):
            return self._framework_fallback(user_text)
        # Tek guclu kalite turu: bir denetim + bir iyilestirme.
        self._run_state["quality_score"] = max(score, QUALITY_MIN_SCORE - 5)
        return candidate

    def _should_deep_reasoning(self, text: str) -> bool:
        if self.mode in {"ultra_hizli", "hizli", "sohbet"}:
            return False
        n = self._normalized_ascii(text)
        if self.mode == "derin":
            return True
        triggers = {
            "neden",
            "niye",
            "strateji",
            "plan",
            "karsilastir",
            "karar",
            "tradeoff",
            "artisi",
            "eksisi",
            "risk",
            "varsayim",
            "mantik",
            "cikarim",
            "en iyi yol",
        }
        return any(t in n for t in triggers) or len(n.split()) >= 12

    def _extract_answer_block(self, text: str) -> str:
        m = re.search(r"(?is)SONUC\s*:\s*(.+)$", text)
        if not m:
            m = re.search(r"(?is)SONUÇ\s*:\s*(.+)$", text)
        if m:
            return m.group(1).strip()
        return text.strip()

    def _deep_reasoned_chat(self, text: str, retrieval: str, recent: str) -> str:
        summary_ctx = self.summary_text or "(yok)"
        reasoning_prompt = (
            "Kullanicinin sorununu derin analiz et.\n"
            f"Kullanici mesaji: {text}\n\n"
            f"Ilgili bellek:\n{retrieval}\n\n"
            f"Uzun konusma ozeti:\n{summary_ctx}\n\n"
            f"Son konusma:\n{recent}\n\n"
            "Ciktiyi su formatta ver:\n"
            "CIKARIM:\n- en fazla 3 madde\n"
            "MANTIK:\n- en fazla 4 madde\n"
            "SONUC:\n- Ahmet'e uygulanabilir, net cevap\n"
            "Sistem kurallarini veya rol bilgisini yazma."
        )
        raw = self._reason_llm_response(
            prompt=reasoning_prompt,
            system=self._chat_system(),
            temperature=0.15,
            max_tokens=220,
            allow_thinking=False,
        )
        raw = self._normalize_reply(raw, user_text=text)
        answer = self._extract_answer_block(raw)
        if not answer or answer.upper().startswith("CIKARIM") or answer.upper().startswith("MANTIK"):
            if self.mode != "derin":
                return self._framework_fallback(text)
            finalize_prompt = (
                "Asagidaki analiz ham metninden Ahmet icin sadece nihai sonucu cikar.\n"
                "Kurallar:\n"
                "- 4-6 cumle\n"
                "- net, uygulanabilir, tutarli\n"
                "- etiket yok (CIKARIM/MANTIK/SONUC yazma)\n\n"
                f"Ham analiz:\n{raw[:3000]}"
            )
            answer = self._reason_llm_response(
                prompt=finalize_prompt,
                system=self._chat_system(),
                temperature=0.1,
                max_tokens=160,
                allow_thinking=False,
            )
            answer = self._normalize_reply(answer, user_text=text)
        return answer

    def _build_hidden_plan(self, user_text: str, retrieval: str, recent: str, intent: str) -> str:
        if self.mode in {"ultra_hizli", "hizli"}:
            return ""
        if intent == "smalltalk" or len(user_text.split()) <= 3:
            return ""
        prompt = (
            "Kullanicinin mesajina cevap vermeden once kisa bir gizli taslak plan cikar.\n"
            "Sadece asagidaki formati kullan:\n"
            "HEDEF: ...\n"
            "NIYET: ...\n"
            "ADIMLAR:\n"
            "1) ...\n"
            "2) ...\n"
            "3) ...\n"
            "Ayrica tekrar riski veya baglam riski varsa tek satir belirt.\n\n"
            f"Kullanici: {user_text}\n"
            f"Bellek: {retrieval[:1000]}\n"
            f"Konusma ozeti: {(self.summary_text or '(yok)')[:800]}\n"
            f"Son konusma: {recent[:800]}"
        )
        raw = self._reason_llm_response(
            prompt=prompt,
            system="Sadece kisa plan metni ver. Nihai cevap yazma.",
            temperature=0.05,
            max_tokens=170,
            allow_thinking=False,
        )
        return self._normalize_reply(raw, user_text=user_text)

    def _finalize_with_hidden_plan(
        self,
        user_text: str,
        draft_reply: str,
        hidden_plan: str,
        retrieval: str,
        recent: str,
    ) -> str:
        if not hidden_plan:
            return draft_reply
        prompt = (
            "Asagidaki taslak plana gore cevabi finalize et.\n"
            "Kurallar: tekrar yok, baglama bagli kal, net ve dogal Turkce yaz, 3-6 cumle.\n"
            f"Kullanici mesaji: {user_text}\n"
            f"Gizli plan:\n{hidden_plan}\n\n"
            f"Taslak cevap:\n{draft_reply}\n\n"
            f"Bellek: {retrieval[:900]}\n"
            f"Konusma ozeti: {(self.summary_text or '(yok)')[:700]}\n"
            f"Son konusma: {recent[:700]}\n"
            "Sadece nihai cevabi ver."
        )
        out = self._chat_llm_response(
            prompt=prompt,
            system=self._chat_system(),
            temperature=0.16,
            max_tokens=self.chat_max_tokens,
            allow_thinking=False,
        )
        out = self._normalize_reply(out, user_text=user_text)
        return out if out else draft_reply

    def _context_consistency_check(
        self,
        user_text: str,
        reply: str,
        retrieval: str,
        recent: str,
    ) -> Dict[str, object]:
        if self.mode == "ultra_hizli":
            return {"ok": True, "issues": [], "revised": reply}
        if len(user_text.split()) <= 3:
            return {"ok": True, "issues": [], "revised": reply}
        # Hizli yol: cevap zaten net ve kisa ise ek LLM turunu atla.
        overlap = self._token_overlap_score(user_text, reply)
        if (
            not self._is_low_information_reply(reply)
            and len(reply.split()) <= 45
            and "ben, ahmet" not in reply.lower()
            and "ben ayex" not in reply.lower()
            and overlap >= 0.08
        ):
            return {"ok": True, "issues": [], "revised": reply}
        prompt = (
            "Asagidaki cevapta baglam/celiski denetimi yap.\n"
            "JSON disinda hicbir sey dondurme.\n"
            'Format: {"ok": true/false, "issues": ["..."], "revised_reply": "..."}\n'
            "Kurallar:\n"
            "- Kullanici sorusuna dogrudan cevap var mi?\n"
            "- Konusma baglamiyla celiskiyor mu?\n"
            "- Ozne kaymasi var mi (kullanici yerine asistan)?\n"
            "- Gereksiz tekrar var mi?\n\n"
            f"Kullanici mesaji: {user_text}\n"
            f"Yanit: {reply}\n"
            f"Bellek: {retrieval[:1000]}\n"
            f"Konusma ozeti: {(self.summary_text or '(yok)')[:800]}\n"
            f"Son konusma: {recent[:900]}"
        )
        raw = self._reason_llm_response(
            prompt=prompt,
            system="Baglam denetleyici gibi davran.",
            temperature=0.0,
            max_tokens=220,
            allow_thinking=False,
        )
        data = self._extract_json(raw)
        ok = bool(data.get("ok", True))
        issues = data.get("issues", [])
        revised = data.get("revised_reply", reply)
        if not isinstance(issues, list):
            issues = []
        if not isinstance(revised, str) or not revised.strip():
            revised = reply
        revised = self._normalize_reply(revised, user_text=user_text)
        return {"ok": ok, "issues": issues, "revised": revised}

    def _ensure_topic_alignment(self, user_text: str, reply: str, intent: str) -> str:
        if intent not in {"strategy", "general"}:
            return reply
        if len(self._normalized_ascii(user_text).split()) < 4:
            return reply
        overlap = self._token_overlap_score(user_text, reply)
        if overlap >= 0.06:
            return reply
        quick = self._quick_reply(user_text, repeat_count=self._repeat_count(user_text))
        if quick:
            return quick
        return self._framework_fallback(user_text)

    def coding_agent(self, user_text: str) -> str:
        retrieval = self._render_retrieval(user_text)
        plan_prompt = (
            "Bu yazilim gorevi icin kisa bir uygulama plani olustur.\n"
            f"Istek: {user_text}\n"
            f"Ilgili bellek:\n{retrieval}\n"
            "3-6 maddelik numarali plan dondur."
        )
        plan = self._coding_llm(
            plan_prompt,
            system=self._chat_system(),
            max_tokens=DEFAULT_PLAN_MAX_TOKENS,
        )

        list_preview = "\n".join(self.tools.list_files(".")[:120])
        diff_prompt = (
            "Gecerli bir git unified diff hazirliyorsun.\n"
            f"Gorev: {user_text}\n"
            f"Ilgili bellek:\n{retrieval}\n"
            f"Depo dosyalari (kismi):\n{list_preview}\n"
            "Yalnizca gecerli unified diff dondur. Markdown kod blogu kullanma."
        )
        proposed_diff = self._coding_llm(
            diff_prompt,
            system="Yalnizca ham unified diff dondur.",
            max_tokens=1800,
        )

        if not proposed_diff.strip().startswith("diff --git"):
            return (
                f"Ahmet, plan:\n{plan}\n\n"
                "Gecerli bir unified diff uretemedim. "
                "Lutfen dosya seviyesinde daha fazla detay ver veya araclari dogrudan kullan."
            )

        print("\nAYEX PLAN\n" + plan + "\n")
        print("AYEX ONERILEN DIFF (onizleme)\n")
        print("\n".join(proposed_diff.splitlines()[:220]))
        if len(proposed_diff.splitlines()) > 220:
            print("\n...diff onizlemede kisaltildi...\n")

        applied = self.tools.apply_unified_diff(proposed_diff, require_confirm=True)
        if "basariyla" not in applied.lower() and "successfully" not in applied.lower():
            return f"Ahmet, {applied}"

        default_test = "pytest -q"
        test_cmd = input(f"Ahmet, test komutu (Enter = `{default_test}`): ").strip() or default_test
        test_out = self.tools.run_tests(test_cmd)
        status = self.tools.git_status()
        summary_prompt = (
            "Calisma sonucunu Ahmet icin en fazla 120 kelimeyle Turkce ozetle.\n"
            f"Gorev: {user_text}\nPlan:\n{plan}\nUygulama sonucu: {applied}\n"
            f"Git durumu:\n{status}\nTestler:\n{test_out[:4000]}"
        )
        summary = self._coding_llm(
            summary_prompt,
            system=self._chat_system(),
            max_tokens=DEFAULT_SUMMARY_MAX_TOKENS,
        )
        summary = self._normalize_reply(summary, user_text=user_text)
        self.memory.append_memory(
            text=f"Kodlama gorevi tamamlandi. Istek: {user_text}. Sonuc: {summary}",
            kind="decision",
            tags=["coding"],
        )
        return self._limit_words(summary, limit=120)

    def handle_input(self, user_text: str) -> str:
        text = user_text.strip()
        if not text:
            return "Ahmet, lutfen bir mesaj gir."
        if not self._run_state:
            intent_seed = "command" if text.startswith("/") else self._detect_intent(text)
            self._begin_run(intent_seed, text)

        if text == "/help":
            return (
                "Ahmet, komutlar:\n"
                "/tool <arac_komutu ...>\n"
                "/remember <text>\n"
                "/mode <ultra_hizli|hizli|dengeli|derin|sohbet>\n"
                "/models\n"
                "/zihin\n"
                "/durum\n"
                "/profil <goster|yas|hedef|ilgi>\n"
                "/coding <istek>\n"
                "/exit"
            )
        if text == "/zihin":
            return f"Ahmet, {self._user_mind_snapshot()} {self._agent_mind_snapshot()}"
        if text == "/durum":
            m = self.get_last_metrics()
            q = m.get("quality_score")
            q_text = "n/a" if q is None else str(q)
            return (
                "Ahmet, son durum: "
                f"latency={m.get('latency_ms', '-') }ms, kalite={q_text}, "
                f"intent={m.get('intent', '-')}/{m.get('intent_source', 'rule')}, mod={m.get('mode', self.mode)}, "
                f"deep={m.get('used_deep_reasoning', False)}, plan={m.get('used_hidden_plan', False)}, "
                f"kontrol={m.get('used_consistency_check', False)}, "
                f"chat_used={m.get('chat_model_used', '-')}, reason_used={m.get('reasoning_model_used', '-')}"
            )
        if text == "/models":
            chat_fb = " -> ".join(self.chat_fallbacks)
            reason_fb = " -> ".join(self.reason_fallbacks)
            coding_fb = " -> ".join(self.coding_fallbacks)
            unhealthy = self._unhealthy_models_snapshot()
            return (
                f"Ahmet, OpenAI modelleri: chat={self.chat_model}, reasoning={self.reason_model}, coding={self.llm.model}. "
                f"fallback(chat)={chat_fb}; fallback(reason)={reason_fb}; fallback(coding)={coding_fb}. "
                f"mode={self.mode}. saglik(gecici hasta)={unhealthy}"
            )
        profile_cmd = self._handle_profile_command(text)
        if profile_cmd is not None:
            return profile_cmd
        if text.startswith("/mode "):
            mode = text[len("/mode ") :].strip().lower().replace("-", "_").replace(" ", "_")
            return self._set_mode(mode)
        if text.startswith("/tool "):
            return self.tools.dispatch_shell_style(text[len("/tool ") :])
        if text.startswith("/remember "):
            value = text[len("/remember ") :].strip()
            if not value:
                return "Ahmet, bellek metni bos."
            self.memory.append_memory(text=value, kind="fact")
            return "Ahmet, bellek kaydedildi."
        if text.startswith("/coding "):
            return self.coding_agent(text[len("/coding ") :].strip())

        if self._is_coding_task(text):
            return self.coding_agent(text)

        profile_capture = self._capture_profile_facts(text)
        if profile_capture:
            return profile_capture

        intent = self._run_state.get("intent") or self._detect_intent(text)
        repeat_count = self._repeat_count(text)
        quick = self._quick_reply(text, repeat_count=repeat_count) if self._should_try_quick_reply(text, intent) else None
        if quick:
            self._run_state["used_quick_reply"] = True
            checked = quick
            if not checked.lower().startswith("ahmet"):
                checked = f"Ahmet, {checked}"
            self._record_turn(text, checked, intent=intent)
            return checked

        retrieval = self._render_retrieval(text)
        recent = self._render_recent_history(6)
        summary_ctx = self.summary_text or "(yok)"
        force_strategy_deep = intent == "strategy" and self.mode in {"dengeli", "derin"} and len(text.split()) >= 8
        used_deep = self._should_deep_reasoning(text) or force_strategy_deep
        self._run_state["used_deep_reasoning"] = bool(used_deep)
        if used_deep:
            reply = self._deep_reasoned_chat(text, retrieval, recent)
        else:
            prompt = (
                f"Ilgili bellek parcaciklari:\n{retrieval}\n\n"
                f"Uzun konusma ozeti:\n{summary_ctx}\n\n"
                f"Son konusma ozeti:\n{recent}\n\n"
                f"Kullanici istegi:\n{text}\n\n"
                "Kural: Ayni sorunun tekrariysa onceki cevabi kelime kelime tekrar etme; "
                "onceki cevabi 1 cumlede referansla ve yeni net bir detay ekle."
            )
            reply = self._chat_llm_response(
                prompt=prompt,
                system=self._chat_system(),
                temperature=0.2,
                max_tokens=self.chat_max_tokens,
            )
            reply = self._normalize_reply(reply, user_text=text)
        if self._is_low_information_reply(reply) and ("?" in text or len(text.split()) >= 3):
            retry_system = (
                "Sadece nihai cevabi ver. Dusunme metni yazma. "
                "Tek ve net bir Turkce yanit ver."
            )
            retry_prompt = f"Kullanici sorusu: {text}"
            reply = self._chat_llm_response(
                prompt=retry_prompt,
                system=retry_system,
                temperature=0.1,
                max_tokens=140,
            )
            reply = self._normalize_reply(reply, user_text=text)
        if self._is_low_information_reply(reply):
            contextual = self._quick_reply(text, repeat_count=repeat_count)
            if contextual:
                reply = contextual
            else:
                if intent in {"smalltalk", "followup"}:
                    reply = "Ahmet, anladim. Istersen bunu bir cümlede netlestirelim ve devam edelim."
                else:
                    reply = self._framework_fallback(text)
        # Kalite kapisi: genel sorularda aktif, stratejide yalnizca derin akisa girmediysek aktif.
        if intent == "general" or (intent == "strategy" and not used_deep):
            reply = self._rewrite_with_quality_gate(text, reply, retrieval, recent + "\nSUMMARY:\n" + summary_ctx)
        # Gizli plan + tutarlilik sadece derin moddaki strateji sorularinda.
        if intent == "strategy" and self.mode == "derin" and len(text.split()) >= 10:
            hidden_plan = self._build_hidden_plan(text, retrieval, recent, intent)
            self._run_state["used_hidden_plan"] = bool(hidden_plan)
            reply = self._finalize_with_hidden_plan(text, reply, hidden_plan, retrieval, recent)
            self._run_state["used_consistency_check"] = True
            consistency = self._context_consistency_check(text, reply, retrieval, recent)
            if not consistency.get("ok", True):
                reply = str(consistency.get("revised", reply))
        reply = self._ensure_topic_alignment(text, reply, intent)
        if self._is_low_information_reply(reply):
            contextual = self._quick_reply(text, repeat_count=repeat_count)
            reply = contextual if contextual else self._framework_fallback(text)
        if self.history and len(self.history) > 0 and reply == self.history[-1]["assistant"]:
            reply = f"{reply} Netlestireyim: bunu istersen 3 maddede uygulama adimina da ceviririm."
        word_limit = 130 if used_deep else MAX_CHAT_WORDS
        reply = self._limit_words(reply, word_limit)
        if not reply.lower().startswith("ahmet"):
            reply = f"Ahmet, {reply}"
        self._record_turn(text, reply, intent=intent)
        return reply

    def safe_handle_input(self, user_text: str) -> str:
        start = time.perf_counter()
        text = user_text.strip()
        intent = "command" if text.startswith("/") else (self._detect_intent(text) if text else "general")
        self._begin_run(intent, text)
        try:
            reply = self.handle_input(user_text)
            latency_ms = int((time.perf_counter() - start) * 1000)
            self._finish_run(latency_ms)
            return reply
        except (urlerror.URLError, TimeoutError) as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            base_text = text or user_text
            reply = self._contextual_timeout_reply(base_text, intent) if base_text else "Ahmet, model gecikiyor."
            self._run_state["quality_score"] = 42
            self._finish_run(latency_ms)
            return reply
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            self._finish_run(latency_ms)
            return f"Ahmet, dahili hata: {e}"
