from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from backend.src.config.env import BackendSettings, load_settings
from backend.src.intel.intel_archive import IntelArchive
from backend.src.intel.intel_service import IntelService
from backend.src.intel.intel_store import IntelStore
from backend.src.services.agent_mode import AgentModeService
from backend.src.services.agent_registry import AgentRegistry
from backend.src.services.anthropic_client import AnthropicClient
from backend.src.services.auth_service import AuthService
from backend.src.services.chat_store import ChatStore
from backend.src.services.cost_guard import CostGuardService
from backend.src.services.intent_router import IntentRouter
from backend.src.services.long_memory import LongMemoryService
from backend.src.services.memory_summarizer import MemorySummarizer
from backend.src.services.model_service import ModelService
from backend.src.services.profile_service import ProfileService
from backend.src.services.response_style import ResponseStyleService
from backend.src.services.response_orchestrator import ResponseOrchestrator
from backend.src.services.stt_service import SpeechToTextService
from backend.src.services.tool_router import ToolRouter
from backend.src.services.tts_service import TextToSpeechService
from backend.src.services.voice_response import VoiceResponseService
from backend.src.tools.registry import ToolRegistry
from backend.src.utils.logging import get_logger, log_event

logger = get_logger(__name__)


@dataclass
class BackendServices:
    settings: BackendSettings
    agents: AgentRegistry
    stt: SpeechToTextService
    tts: TextToSpeechService
    intents: IntentRouter
    memory: MemorySummarizer
    tools: ToolRouter
    voice: VoiceResponseService
    orchestrator: ResponseOrchestrator
    model: ModelService
    chat_store: ChatStore
    profile: ProfileService
    auth: AuthService
    style: ResponseStyleService
    long_memory: LongMemoryService
    agent_mode: AgentModeService
    intel: IntelService
    cost_guard: CostGuardService


def build_services() -> BackendServices:
    settings = load_settings()
    openai_primary = (os.environ.get("OPENAI_API_KEY") or "").strip()
    openai_legacy = (os.environ.get("AYEX_API_KEY") or "").strip()
    log_event(logger, "bootstrap_start", mode="direct_provider_path", web_mvp_only=settings.web_mvp_only)
    if openai_primary:
        log_event(logger, "openai_key_source", source="OPENAI_API_KEY")
    elif openai_legacy:
        logger.warning("OPENAI_KEY_SOURCE AYEX_API_KEY (legacy fallback)")
    else:
        logger.error("OPENAI_KEY_MISSING OPENAI_API_KEY is empty (AYEX_API_KEY fallback also empty)")
    agents = AgentRegistry()
    stt = SpeechToTextService(settings)
    tts = TextToSpeechService(settings)
    intents = IntentRouter()
    memory = MemorySummarizer(settings)
    tool_registry = ToolRegistry()
    tools = ToolRouter(registry=tool_registry)
    voice = VoiceResponseService()
    anthropic_client = None
    if settings.anthropic_api_key:
        try:
            anthropic_client = AnthropicClient(api_key=settings.anthropic_api_key)
            log_event(logger, "anthropic_client", status="initialized")
        except Exception as e:
            logger.warning("ANTHROPIC_CLIENT_FAILED error=%s", str(e))
    model_service = ModelService(settings, anthropic_client=anthropic_client)
    chat_store = ChatStore(settings)
    profile = ProfileService(settings)
    auth = AuthService()
    style = ResponseStyleService()
    long_memory = LongMemoryService(settings)
    long_memory.sync_profile(profile.load())
    agent_mode = AgentModeService(model_service=model_service, tools=tools)
    intel_archive = IntelArchive(data_dir=Path(settings.data_dir))
    intel_store = IntelStore(persist_path=Path(settings.data_dir) / "intel_events.json", archive=intel_archive)
    intel = IntelService(intel_store, openai_client=model_service.openai, profile_loader=profile.load)
    cost_guard = CostGuardService(settings)
    orchestrator = ResponseOrchestrator(
        stt_service=stt,
        tts_service=tts,
        intent_router=intents,
        tool_router=tools,
        voice_response_service=voice,
        model_service=model_service,
    )
    log_event(
        logger,
        "bootstrap_ready",
        chat_model=settings.ayex_chat_model,
        reasoning_model=settings.ayex_reasoning_model,
        power_model=settings.ayex_power_model,
        fast_model=settings.ayex_fast_model,
        intel_prompt_max_events=settings.intel_prompt_max_events,
        intel_prompt_max_chars=settings.intel_prompt_max_chars,
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
        model=model_service,
        chat_store=chat_store,
        profile=profile,
        auth=auth,
        style=style,
        long_memory=long_memory,
        agent_mode=agent_mode,
        intel=intel,
        cost_guard=cost_guard,
    )
