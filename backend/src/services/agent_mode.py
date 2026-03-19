from __future__ import annotations

from dataclasses import dataclass

from backend.src.services.openclaw_service import OpenClawResult, OpenClawService
from backend.src.services.tool_router import ToolRouteResult, ToolRouter


@dataclass(frozen=True)
class AgentModeResult:
    final: OpenClawResult
    plan: OpenClawResult
    tools: ToolRouteResult


class AgentModeService:
    def __init__(self, openclaw: OpenClawService, tools: ToolRouter):
        self.openclaw = openclaw
        self.tools = tools

    def run(
        self,
        *,
        text: str,
        workspace: str | None,
        model: str | None,
        profile_context: str | None,
        memory_context: str | None,
        response_style: str = "deep",
    ) -> AgentModeResult:
        # 1) Goal -> short plan from model
        plan_prompt = (
            "Asagidaki hedef icin en fazla 3 adimlik net plan cikar.\n"
            f"Hedef: {text}"
        )
        plan_res = self.openclaw.run_action(
            plan_prompt,
            workspace=workspace,
            model=model,
            profile_context=profile_context,
            memory_context=memory_context,
            response_style="deep",
            route_name="agent_plan",
        )

        # 2) Tool calls (max 3)
        tool_res = self.tools.run_agent_tools(text=text, max_calls=3)
        evidence = tool_res.evidence_text()

        # 3) Final synthesis
        final_prompt = (
            f"Gorev: {text}\n\n"
            f"Plan:\n{plan_res.text}\n\n"
            f"Kanit:\n{evidence or 'Tool verisi yok.'}\n\n"
            "Yanitini uygulanabilir bir rapor formatinda ver."
        )
        final = self.openclaw.run_action(
            final_prompt,
            workspace=workspace,
            model=model,
            profile_context=profile_context,
            memory_context=memory_context,
            response_style=response_style,
            route_name="agent_final",
        )
        return AgentModeResult(final=final, plan=plan_res, tools=tool_res)
