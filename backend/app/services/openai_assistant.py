from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
from time import perf_counter
from typing import Callable, Literal

from agents import Agent, ModelSettings, RunConfig, RunContextWrapper, Runner, function_tool

from app.services.assistant_service import AssistantProviderResult
from app.services.assistant_tools import AssistantSource, KaushalToolset, ToolResult


logger = logging.getLogger(__name__)
RelativePeriod = Literal[
    "today", "yesterday", "this_week", "last_week", "last_7_days", "last_30_days"
]

AGENT_INSTRUCTIONS = """You are Kaushal Assistant, the operational intelligence assistant for KaushalWatch.

For every question about centre operations, analyses, attendance, practical work, discrepancies,
escalations, evidence, or readiness, use the available KaushalWatch tools before answering. Base
every operational statement only on tool results from the selected centre. Never invent workers,
identities, events, evidence, metrics, dates, or conclusions. Attendance tracking is anonymous;
when asked about a named worker, explain that KaushalWatch does not retain worker identity.

Distinguish recorded observations from system-generated conclusions and unavailable information.
Use cautious language for vision output: “the system detected” or “the analysis flagged,” not claims
of certainty. Preserve stored confidence, detector authority, camera trust, status, severity, and
escalation policy. Do not recalculate severity. If a tool has no data or fails, say so plainly.
Keep answers concise by default and recommend human review for consequential workplace decisions.
"""


@dataclass
class ProviderRunContext:
    toolset: KaushalToolset
    centre_id: str
    sources: list[AssistantSource] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


def _invoke_tool(
    wrapper: RunContextWrapper[ProviderRunContext],
    name: str,
    operation: Callable[[], ToolResult],
) -> str:
    started = perf_counter()
    logger.info("assistant tool called: %s", name)
    try:
        result = operation()
        wrapper.context.sources.extend(result.sources)
        status = "success"
        payload = result.data
    except Exception:
        logger.exception("assistant tool failed: %s", name)
        status = "error"
        payload = {
            "available": False,
            "error": "KaushalWatch data could not be retrieved for this tool call.",
        }
    duration_ms = max(0, round((perf_counter() - started) * 1000))
    wrapper.context.tool_calls.append(
        {"name": name, "status": status, "duration_ms": duration_ms}
    )
    logger.info("assistant tool completed: %s in %dms", name, duration_ms)
    return json.dumps(payload, ensure_ascii=False, default=str)


@function_tool
def get_centre_overview(ctx: RunContextWrapper[ProviderRunContext]) -> str:
    """Get current verification, case, and escalation state for the selected centre."""
    return _invoke_tool(
        ctx,
        "get_centre_overview",
        lambda: ctx.context.toolset.get_centre_overview(ctx.context.centre_id),
    )


@function_tool
def get_runtime_readiness(ctx: RunContextWrapper[ProviderRunContext]) -> str:
    """Get detector and evidence runtime readiness for KaushalWatch."""
    return _invoke_tool(
        ctx,
        "get_runtime_readiness",
        lambda: ctx.context.toolset.get_runtime_readiness(ctx.context.centre_id),
    )


@function_tool
def get_operational_history(
    ctx: RunContextWrapper[ProviderRunContext],
    period: RelativePeriod = "last_7_days",
    analysis_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get recorded analyses for a concrete relative or explicit date range.

    Args:
        period: Relative date range to query.
        analysis_type: Optional stored type such as attendance, practical_work, or infrastructure.
        start_date: Optional explicit start date in YYYY-MM-DD form.
        end_date: Optional explicit inclusive end date in YYYY-MM-DD form.
    """
    return _invoke_tool(
        ctx,
        "get_operational_history",
        lambda: ctx.context.toolset.get_operational_history(
            ctx.context.centre_id, period, analysis_type, start_date, end_date
        ),
    )


@function_tool
def get_analysis_details(
    ctx: RunContextWrapper[ProviderRunContext], analysis_id: str
) -> str:
    """Get one recorded analysis that belongs to the selected centre.

    Args:
        analysis_id: Persisted KaushalWatch analysis ID.
    """
    return _invoke_tool(
        ctx,
        "get_analysis_details",
        lambda: ctx.context.toolset.get_analysis_details(ctx.context.centre_id, analysis_id),
    )


@function_tool
def get_attendance_summary(
    ctx: RunContextWrapper[ProviderRunContext],
    period: RelativePeriod = "last_7_days",
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get anonymous attendance analyses, metrics, and discrepancy cases.

    Args:
        period: Relative date range to query.
        start_date: Optional explicit start date in YYYY-MM-DD form.
        end_date: Optional explicit inclusive end date in YYYY-MM-DD form.
    """
    return _invoke_tool(
        ctx,
        "get_attendance_summary",
        lambda: ctx.context.toolset.get_attendance_summary(
            ctx.context.centre_id, period, start_date, end_date
        ),
    )


@function_tool
def get_practical_work_summary(
    ctx: RunContextWrapper[ProviderRunContext],
    period: RelativePeriod = "last_7_days",
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get practical-work activity analyses and cases for a date range.

    Args:
        period: Relative date range to query.
        start_date: Optional explicit start date in YYYY-MM-DD form.
        end_date: Optional explicit inclusive end date in YYYY-MM-DD form.
    """
    return _invoke_tool(
        ctx,
        "get_practical_work_summary",
        lambda: ctx.context.toolset.get_practical_work_summary(
            ctx.context.centre_id, period, start_date, end_date
        ),
    )


@function_tool
def get_escalations(
    ctx: RunContextWrapper[ProviderRunContext],
    status: str = "unresolved",
    severity: str | None = None,
) -> str:
    """Get cases and the existing policy-calculated escalation state.

    Args:
        status: unresolved, all, or a stored case status.
        severity: Optional stored severity filter.
    """
    return _invoke_tool(
        ctx,
        "get_escalations",
        lambda: ctx.context.toolset.get_escalations(
            ctx.context.centre_id, status, severity
        ),
    )


@function_tool
def get_case_evidence(
    ctx: RunContextWrapper[ProviderRunContext], case_id: str
) -> str:
    """Get compact evidence and review metadata for one centre-owned case.

    Args:
        case_id: Persisted KaushalWatch compliance case ID.
    """
    return _invoke_tool(
        ctx,
        "get_case_evidence",
        lambda: ctx.context.toolset.get_case_evidence(ctx.context.centre_id, case_id),
    )


class OpenAIAssistantProvider:
    def __init__(
        self,
        *,
        toolset: KaushalToolset,
        runner=Runner,
        model: str | None = None,
    ):
        self.toolset = toolset
        self.runner = runner
        self.agent = Agent[ProviderRunContext](
            name="Kaushal Assistant",
            instructions=AGENT_INSTRUCTIONS,
            model=model or os.getenv("KAUSHAL_AI_MODEL", "gpt-5-mini"),
            model_settings=ModelSettings(tool_choice="required", parallel_tool_calls=False),
            tools=[
                get_centre_overview,
                get_runtime_readiness,
                get_operational_history,
                get_analysis_details,
                get_attendance_summary,
                get_practical_work_summary,
                get_escalations,
                get_case_evidence,
            ],
        )

    async def run(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        centre_id: str,
    ) -> AssistantProviderResult:
        context = ProviderRunContext(toolset=self.toolset, centre_id=centre_id)
        inputs = [*history, {"role": "user", "content": message}]
        result = await self.runner.run(
            self.agent,
            input=inputs,
            context=context,
            run_config=RunConfig(
                workflow_name="Kaushal Assistant",
                trace_include_sensitive_data=False,
            ),
        )
        logger.info("assistant agent completed for centre %s", centre_id)
        return AssistantProviderResult(
            message=str(result.final_output or ""),
            sources=context.sources,
            tool_calls=context.tool_calls,
        )
