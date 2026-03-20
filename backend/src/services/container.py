from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from backend.src.config.env import BackendSettings, load_settings
from backend.src.intel.intel_service import IntelService
from backend.src.intel.intel_store import IntelStore
from backend.src.memory.manager import MemoryManager
from backend.src.services.agent_mode import AgentModeService
from backend.src.services.agent_registry import AgentRegistry
from backend.src.services.chat_store import ChatStore
from backend.src.services.cost_guard import CostGuardService
from backend.src.services.intent_router import IntentRouter
from backend.src.services.long_memory import LongMemoryService
from backend.src.services.openclaw_service import OpenClawService
from backend.src.services.profile_service import ProfileService
from backend.src.services.response_style import ResponseStyleService
from backend.src.services.response_orchestrator import ResponseOrchestrator
from backend.src.services.stt_service import SpeechToTextService
from backend.src.services.tool_router import ToolRouter
from backend.src.services.tts_service import TextToSpeechService
from backend.src.services.voice_response import VoiceResponseService
from backend.src.tools.registry import ToolRegistry
from backend.src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BackendServices:
    settings: BackendSettings
    agents: AgentRegistry
    stt: SpeechToTextService
    tts: TextToSpeechService
    intents: IntentRouter
    memory: MemoryManager
    tools: ToolRouter
    voice: VoiceResponseService
    orchestrator: ResponseOrchestrator
    openclaw: OpenClawService
    chat_store: ChatStore
    profile: ProfileService
    style: ResponseStyleService
    long_memory: LongMemoryService
    agent_mode: AgentModeService
    intel: IntelService
    cost_guard: CostGuardService


def build_services() -> BackendServices:
    settings = load_settings()
    openai_primary = (os.environ.get("OPENAI_API_KEY") or "").strip()
    openai_legacy = (os.environ.get("AYEX_API_KEY") or "").strip()
    if settings.openclaw_enabled:
        logger.info("CONFIG_MODE openclaw_enabled=true")
    else:
        logger.info("CONFIG_MODE openclaw_enabled=false (direct OpenAI primary path)")
    if openai_primary:
        logger.info("OPENAI_KEY_SOURCE OPENAI_API_KEY")
    elif openai_legacy:
        logger.warning("OPENAI_KEY_SOURCE AYEX_API_KEY (legacy fallback)")
    else:
        logger.error("OPENAI_KEY_MISSING OPENAI_API_KEY is empty (AYEX_API_KEY fallback also empty)")
    agents = AgentRegistry()
    stt = SpeechToTextService(settings)
    tts = TextToSpeechService(settings)
    intents = IntentRouter()
    memory = MemoryManager()
    tool_registry = ToolRegistry()
    tools = ToolRouter(registry=tool_registry)
    voice = VoiceResponseService()
    openclaw = OpenClawService(settings, agents=agents)
    chat_store = ChatStore(settings)
    profile = ProfileService(settings)
    style = ResponseStyleService()
    long_memory = LongMemoryService(settings)
    long_memory.sync_profile(profile.load())
    agent_mode = AgentModeService(openclaw=openclaw, tools=tools)
    intel_store = IntelStore(persist_path=Path(settings.data_dir) / "intel_events.json")
    intel = IntelService(intel_store, openai_client=openclaw.openai)
    _seed_intel(intel)
    cost_guard = CostGuardService(settings)
    orchestrator = ResponseOrchestrator(
        stt_service=stt,
        tts_service=tts,
        intent_router=intents,
        tool_router=tools,
        voice_response_service=voice,
        openclaw_service=openclaw,
    )
    return BackendServices(
        settings=settings,
        agents=agents,
        stt=stt,
        tts=tts,
        intents=intents,
        memory=memory,
        tools=tools,
        voice=voice,
        orchestrator=orchestrator,
        openclaw=openclaw,
        chat_store=chat_store,
        profile=profile,
        style=style,
        long_memory=long_memory,
        agent_mode=agent_mode,
        intel=intel,
        cost_guard=cost_guard,
    )


def _seed_intel(intel: IntelService) -> None:
    if intel.store.get_all_events():
        return
    intel.create_event(
        title="Bitcoin rises 5%",
        summary="BTC fiyatı son 24 saatte yaklasik %5 artarak risk istahini yukseltti.",
        category="market",
        importance=9,
        source="seed",
        tags=["btc", "crypto", "market"],
    )
    intel.create_event(
        title="Major data breach reported",
        summary="Buyuk bir teknoloji sirketinde milyonlarca kaydi etkileyen veri sizintisi bildirildi.",
        category="cybersecurity",
        importance=10,
        source="seed",
        tags=["security", "breach"],
    )
    intel.create_event(
        title="AI regulation discussion",
        summary="Politika yapicilar yeni yapay zeka duzenleme cercevelerini tartisiyor.",
        category="policy",
        importance=7,
        source="seed",
        tags=["ai", "regulation"],
    )
    intel.create_event(
        title="Cloud outage impacts services",
        summary="Bolgesel bulut kesintisi bazi SaaS urunlerinde erisim sorunlarina neden oldu.",
        category="infrastructure",
        importance=8,
        source="seed",
        tags=["cloud", "outage"],
    )
    intel.create_event(
        title="Semiconductor supply improves",
        summary="Cip tedarik zincirindeki normalizasyon, donanim teslim surelerini kisaltiyor.",
        category="industry",
        importance=6,
        source="seed",
        tags=["chip", "supply-chain"],
    )
