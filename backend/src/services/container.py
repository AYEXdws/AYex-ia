from __future__ import annotations

from dataclasses import dataclass

from backend.src.config.env import BackendSettings, load_settings
from backend.src.memory.manager import MemoryManager
from backend.src.services.agent_registry import AgentRegistry
from backend.src.services.intent_router import IntentRouter
from backend.src.services.openclaw_service import OpenClawService
from backend.src.services.response_orchestrator import ResponseOrchestrator
from backend.src.services.stt_service import SpeechToTextService
from backend.src.services.tool_router import ToolRouter
from backend.src.services.tts_service import TextToSpeechService
from backend.src.services.voice_response import VoiceResponseService


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


def build_services() -> BackendServices:
    settings = load_settings()
    agents = AgentRegistry()
    stt = SpeechToTextService(settings)
    tts = TextToSpeechService(settings)
    intents = IntentRouter()
    memory = MemoryManager()
    tools = ToolRouter(memory_manager=memory)
    voice = VoiceResponseService()
    openclaw = OpenClawService(settings)
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
    )
