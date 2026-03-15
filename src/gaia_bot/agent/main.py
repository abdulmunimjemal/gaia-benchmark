from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from gaia_bot.agent.constants import ALLOWED_MCP_TOOLS, MCP_SERVER_NAME
from gaia_bot.agent.runtime import SandboxRuntime
from gaia_bot.benchmark.scoring import (
    classify_failure,
    format_benchmark_answer,
    score_prediction,
)
from gaia_bot.config.settings import Settings
from gaia_bot.contracts.basemodels import (
    JudgeOutput,
    PlannerDecision,
    SolverOutput,
    TaskRecord,
    TaskRunResult,
)
from gaia_bot.prompts.constants import SYSTEM_PROMPT
from gaia_bot.prompts.main import direct_prompt, route_prompt, solver_prompt, verifier_prompt
from gaia_bot.routing.main import heuristic_route
from gaia_bot.services.artifacts import TaskArtifactManager


class AgentRuntimeError(RuntimeError):
    """Raised when the Claude Agent SDK returns an invalid or failed result."""


class GaiaAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        api_key = (
            settings.anthropic_api_key.get_secret_value()
            if settings.anthropic_api_key is not None
            else None
        )
        self._anthropic = AsyncAnthropic(api_key=api_key)

    async def smoke_anthropic(self) -> str:
        self.settings.require_service_credentials(require_anthropic=True, require_e2b=False)
        response = await self._anthropic.messages.create(
            model=self.settings.anthropic_model_main,
            max_tokens=32,
            messages=[{"role": "user", "content": "Reply with exactly OK."}],
        )
        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        return "".join(text_blocks).strip()

    async def solve(
        self,
        task: TaskRecord,
        *,
        run_id: str,
        task_workspace: Path,
    ) -> TaskRunResult:
        self.settings.require_service_credentials(require_anthropic=True, require_e2b=False)
        started_at = time.perf_counter()
        retry_count = 0

        planner = await self._route(task)
        artifact_manager = TaskArtifactManager(
            settings=self.settings,
            task=task,
            task_workspace=task_workspace,
            anthropic_client=self._anthropic,
        )
        attachment_summary = ""
        if planner.needs_artifact:
            attachment = await artifact_manager.read_task_attachment()
            if attachment is not None:
                attachment_summary = attachment.excerpt

        solver: SolverOutput
        judge: JudgeOutput
        tool_calls = []

        if (
            planner.route == "direct"
            and planner.risk == "low"
            and not planner.use_verifier
            and not planner.needs_artifact
            and not planner.needs_web
            and not planner.needs_code
        ):
            solver = await self._solve_direct(task, planner)
            final_answer = format_benchmark_answer(
                solver.answer,
                planner.answer_shape,
                question=task.question,
            )
            judge = JudgeOutput(is_sufficient=True, issues=[], revised_answer=final_answer)
        else:
            self.settings.require_service_credentials(require_anthropic=True, require_e2b=True)
            async with SandboxRuntime(self.settings, artifact_manager) as runtime:
                solver = await self._solve_task(
                    task,
                    planner,
                    runtime,
                    attachment_summary=attachment_summary,
                )
                final_answer = format_benchmark_answer(
                    solver.answer,
                    planner.answer_shape,
                    question=task.question,
                )
                judge = JudgeOutput(is_sufficient=True, issues=[], revised_answer=final_answer)

                if planner.use_verifier:
                    judge = await self._verify(task, planner, solver)
                    if not judge.is_sufficient and judge.issues:
                        retry_count += 1
                        solver = await self._solve_task(
                            task,
                            planner,
                            runtime,
                            attachment_summary=attachment_summary,
                            critique=judge.issues,
                        )
                        final_answer = format_benchmark_answer(
                            solver.answer,
                            planner.answer_shape,
                            question=task.question,
                        )
                        judge = await self._verify(task, planner, solver)
                tool_calls = runtime.trace

        final_answer = format_benchmark_answer(
            judge.revised_answer or final_answer,
            planner.answer_shape,
            question=task.question,
        )
        score = score_prediction(final_answer, task.expected_answer)

        result = TaskRunResult(
            run_id=run_id,
            task_id=task.task_id,
            question=task.question,
            answer=final_answer,
            raw_answer=solver.answer,
            scorer_answer=final_answer,
            expected_answer=task.expected_answer,
            score=score,
            passed=(score == 1.0) if score is not None else None,
            route=planner.route,
            risk=planner.risk,
            retry_count=retry_count,
            planner=planner,
            solver=solver,
            judge=judge,
            tool_calls=tool_calls,
            artifacts_used=artifact_manager.observations,
            duration_seconds=time.perf_counter() - started_at,
            metadata=task.metadata,
        )
        result.error_taxonomy = classify_failure(result)
        return result

    async def _route(self, task: TaskRecord) -> PlannerDecision:
        heuristic = heuristic_route(task)
        if heuristic.route == "direct" and heuristic.risk == "low":
            return heuristic
        if heuristic.route == "artifact":
            return heuristic
        if (
            heuristic.route == "code"
            and heuristic.risk == "high"
            and heuristic.needs_web
            and heuristic.needs_code
        ):
            return heuristic

        payload = await self._run_structured_query(
            prompt=route_prompt(task, heuristic),
            output_schema={
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "enum": ["direct", "web", "code", "artifact"],
                    },
                    "risk": {"type": "string", "enum": ["low", "medium", "high"]},
                    "use_verifier": {"type": "boolean"},
                    "needs_web": {"type": "boolean"},
                    "needs_code": {"type": "boolean"},
                    "needs_artifact": {"type": "boolean"},
                    "research_queries": {"type": "array", "items": {"type": "string"}},
                    "working_plan": {"type": "array", "items": {"type": "string"}},
                    "answer_shape": {"type": "string"},
                },
                "required": [
                    "route",
                    "risk",
                    "use_verifier",
                    "needs_web",
                    "needs_code",
                    "needs_artifact",
                    "research_queries",
                    "working_plan",
                    "answer_shape",
                ],
                "additionalProperties": False,
            },
            model=self.settings.anthropic_model_judge,
            max_turns=2,
        )
        routed = PlannerDecision.model_validate(payload)
        if task.attachment_name or task.attachment_path:
            routed.needs_artifact = True
            if routed.route == "direct":
                routed.route = "artifact"
        return routed

    async def _solve_task(
        self,
        task: TaskRecord,
        planner: PlannerDecision,
        runtime: SandboxRuntime,
        *,
        attachment_summary: str = "",
        critique: list[str] | None = None,
    ) -> SolverOutput:
        if planner.route == "direct" and not planner.use_verifier:
            return await self._solve_direct(task, planner)

        server = runtime.create_mcp_server()
        payload = await self._run_structured_query(
            prompt=solver_prompt(
                task,
                planner,
                attachment_summary=attachment_summary,
                critique=critique,
            ),
            output_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "citations": {"type": "array", "items": {"type": "string"}},
                    "reasoning_summary": {"type": "string"},
                },
                "required": ["answer", "confidence", "citations", "reasoning_summary"],
                "additionalProperties": False,
            },
            model=self.settings.anthropic_model_main,
            max_turns=self.settings.max_turns,
            mcp_server=server,
        )
        return SolverOutput.model_validate(payload)

    async def _solve_direct(self, task: TaskRecord, planner: PlannerDecision) -> SolverOutput:
        payload = await self._run_structured_query(
            prompt=direct_prompt(task, planner),
            output_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "citations": {"type": "array", "items": {"type": "string"}},
                    "reasoning_summary": {"type": "string"},
                },
                "required": ["answer", "confidence", "citations", "reasoning_summary"],
                "additionalProperties": False,
            },
            model=self.settings.anthropic_model_main,
            max_turns=2,
        )
        return SolverOutput.model_validate(payload)

    async def _verify(
        self,
        task: TaskRecord,
        planner: PlannerDecision,
        solver: SolverOutput,
    ) -> JudgeOutput:
        payload = await self._run_structured_query(
            prompt=verifier_prompt(task, planner, solver),
            output_schema={
                "type": "object",
                "properties": {
                    "is_sufficient": {"type": "boolean"},
                    "issues": {"type": "array", "items": {"type": "string"}},
                    "revised_answer": {"type": ["string", "null"]},
                },
                "required": ["is_sufficient", "issues", "revised_answer"],
                "additionalProperties": False,
            },
            model=self.settings.anthropic_model_judge,
            max_turns=2,
        )
        return JudgeOutput.model_validate(payload)

    async def _run_structured_query(
        self,
        *,
        prompt: str,
        output_schema: dict[str, Any],
        model: str,
        max_turns: int,
        mcp_server: Any | None = None,
    ) -> dict[str, Any]:
        attempts = max(2, self.settings.retry_attempts + 1)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await self._attempt_structured_query(
                    prompt=prompt,
                    output_schema=output_schema,
                    model=model,
                    max_turns=max_turns,
                    mcp_server=mcp_server,
                )
            except BaseException as exc:
                if isinstance(exc, KeyboardInterrupt | SystemExit):
                    raise
                last_error = _coerce_runtime_error(exc)
                if attempt == attempts:
                    break
                await asyncio.sleep(min(attempt, 3))
        assert last_error is not None
        raise AgentRuntimeError(str(last_error))

    async def _attempt_structured_query(
        self,
        *,
        prompt: str,
        output_schema: dict[str, Any],
        model: str,
        max_turns: int,
        mcp_server: Any | None = None,
    ) -> dict[str, Any]:
        env = self.settings.runtime_env()
        schema_text = json.dumps(output_schema, indent=2)
        structured_prompt = (
            f"{prompt}\n\n"
            "Return only a valid JSON object that matches this JSON Schema exactly.\n"
            "Do not include markdown, explanations, headings, or prose outside the JSON.\n"
            f"Schema:\n{schema_text}\n"
        )
        use_native_schema = mcp_server is None
        options = ClaudeAgentOptions(
            tools=[],
            mcp_servers={MCP_SERVER_NAME: mcp_server} if mcp_server is not None else {},
            allowed_tools=ALLOWED_MCP_TOOLS if mcp_server is not None else [],
            system_prompt=SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            cwd=self.settings.working_directory,
            model=model,
            max_turns=max_turns,
            cli_path=self.settings.claude_cli_path,
            env=env,
            output_format=output_schema if use_native_schema else None,
        )
        result = await _collect_result(query(prompt=structured_prompt, options=options))
        if result.structured_output is not None:
            return result.structured_output
        if result.result is None:
            raise AgentRuntimeError(
                "Claude Agent SDK returned no structured output or text result."
            )
        try:
            return _extract_json_object(result.result)
        except json.JSONDecodeError as exc:
            raise AgentRuntimeError(
                f"Failed to decode Claude Agent SDK output as JSON: {result.result}"
            ) from exc


async def _collect_result(messages: AsyncIterator[Any]) -> ResultMessage:
    final_result: ResultMessage | None = None
    async for message in messages:
        if isinstance(message, ResultMessage):
            final_result = message
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    _ = block.text
    if final_result is None:
        raise AgentRuntimeError("Claude Agent SDK query completed without a ResultMessage.")
    if final_result.is_error:
        raise AgentRuntimeError(
            final_result.result or "Claude Agent SDK reported an unknown error."
        )
    return final_result


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fenced_match:
        return json.loads(fenced_match.group(1))

    if stripped.startswith("{") and stripped.endswith("}"):
        return json.loads(stripped)

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            candidate, end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        tail = stripped[index + end :].strip()
        if not tail:
            return candidate

    raise json.JSONDecodeError("No JSON object found", stripped, 0)


def _coerce_runtime_error(exc: BaseException) -> AgentRuntimeError:
    if isinstance(exc, AgentRuntimeError):
        return exc
    return AgentRuntimeError(f"{type(exc).__name__}: {exc}")


__all__ = ["AgentRuntimeError", "GaiaAgent"]
