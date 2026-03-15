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
    extract_final_answer,
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
from gaia_bot.prompts.main import (
    direct_prompt,
    format_alignment_prompt,
    route_prompt,
    solver_prompt,
    verifier_prompt,
)
from gaia_bot.routing.main import heuristic_route
from gaia_bot.services.artifacts import TaskArtifactManager

# Bare number: digits with optional sign, optional decimal
_BARE_NUMBER_RE = re.compile(r"^[-+]?\d+(\.\d+)?$")


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

    # ------------------------------------------------------------------
    # Main solve entry point
    # ------------------------------------------------------------------

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
        max_judge_retries = 2

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
        tool_calls: list[Any] = []

        is_simple_direct = (
            planner.route == "direct"
            and planner.risk == "low"
            and not planner.needs_artifact
            and not planner.needs_web
            and not planner.needs_code
        )

        if is_simple_direct:
            solver = await self._solve_direct(task, planner)
            judge = await self._verify(task, planner, solver)
            if not judge.is_sufficient and judge.issues and not judge.revised_answer:
                retry_count += 1
                solver = await self._solve_direct(task, planner)
                judge = await self._verify(task, planner, solver)
        else:
            self.settings.require_service_credentials(
                require_anthropic=True, require_e2b=True
            )
            async with SandboxRuntime(self.settings, artifact_manager) as runtime:
                solver = await self._solve_task(
                    task,
                    planner,
                    runtime,
                    attachment_summary=attachment_summary,
                )

                # Run judge — skip for high-confidence low-risk
                should_verify = (
                    solver.confidence != "high"
                    or planner.risk != "low"
                )
                if should_verify:
                    judge = await self._verify(task, planner, solver)

                    while (
                        not judge.is_sufficient
                        and judge.issues
                        and retry_count < max_judge_retries
                    ):
                        retry_count += 1
                        solver = await self._solve_task(
                            task,
                            planner,
                            runtime,
                            attachment_summary=attachment_summary,
                            critique=judge.issues,
                        )
                        judge = await self._verify(task, planner, solver)
                else:
                    judge = JudgeOutput(
                        is_sufficient=True, issues=[], revised_answer=None
                    )

                tool_calls = runtime.trace

        # Last-resort fallback: if the solver punted ("unable to
        # determine" etc.), try once with a direct no-tools prompt.
        # Many answers are in the model's training data.
        pre_format_answer = judge.revised_answer or solver.answer
        if _is_punt_answer(pre_format_answer):
            try:
                fallback_solver = await self._solve_direct(task, planner)
                if not _is_punt_answer(fallback_solver.answer):
                    solver = fallback_solver
                    pre_format_answer = fallback_solver.answer
            except Exception:
                pass  # keep original answer on fallback failure

        # Answer pipeline: judge revision → extract → format → align
        final_answer = extract_final_answer(pre_format_answer)

        # Format alignment: deterministic first, LLM only for complex
        final_answer = await self._format_align(
            task.question, final_answer, planner.answer_shape
        )

        # Deterministic scoring for local eval (GAIA leaderboard has its own)
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

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

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

        try:
            payload = await self._run_structured_query(
                prompt=route_prompt(task, heuristic),
                output_schema={
                    "type": "object",
                    "properties": {
                        "route": {
                            "type": "string",
                            "enum": ["direct", "web", "code", "artifact"],
                        },
                        "risk": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "use_verifier": {"type": "boolean"},
                        "needs_web": {"type": "boolean"},
                        "needs_code": {"type": "boolean"},
                        "needs_artifact": {"type": "boolean"},
                        "research_queries": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "working_plan": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
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
        except AgentRuntimeError:
            # Fall back to heuristic on routing failure
            return heuristic

        if task.attachment_name or task.attachment_path:
            routed.needs_artifact = True
            if routed.route == "direct":
                routed.route = "artifact"
        return routed

    # ------------------------------------------------------------------
    # Solvers
    # ------------------------------------------------------------------

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
                    "confidence": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "reasoning_summary": {"type": "string"},
                },
                "required": [
                    "answer",
                    "confidence",
                    "citations",
                    "reasoning_summary",
                ],
                "additionalProperties": False,
            },
            model=self.settings.anthropic_model_main,
            max_turns=self.settings.max_turns,
            mcp_server=server,
        )
        return SolverOutput.model_validate(payload)

    async def _solve_direct(
        self, task: TaskRecord, planner: PlannerDecision
    ) -> SolverOutput:
        payload = await self._run_structured_query(
            prompt=direct_prompt(task, planner),
            output_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                    },
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "reasoning_summary": {"type": "string"},
                },
                "required": [
                    "answer",
                    "confidence",
                    "citations",
                    "reasoning_summary",
                ],
                "additionalProperties": False,
            },
            model=self.settings.anthropic_model_main,
            max_turns=2,
        )
        return SolverOutput.model_validate(payload)

    # ------------------------------------------------------------------
    # Format alignment — deterministic first, LLM for complex answers
    # ------------------------------------------------------------------

    async def _format_align(
        self,
        question: str,
        answer: str,
        answer_shape: str,
    ) -> str:
        """Align answer format for exact-match scoring."""
        if not answer.strip():
            return answer

        # Step 1: deterministic cleanup as baseline
        cleaned = format_benchmark_answer(
            answer, answer_shape, question=question
        )

        # Step 2: skip LLM for answers already in clean form —
        # bare numbers, single words, and short answers should
        # NEVER be sent through the LLM (it can hallucinate changes)
        if _BARE_NUMBER_RE.fullmatch(cleaned):
            return cleaned
        if len(cleaned.split()) <= 2:
            return cleaned
        if answer_shape == "number":
            return cleaned

        # Step 3: LLM pass only for complex multi-word formatting
        try:
            prompt = format_alignment_prompt(question, cleaned, answer_shape)
            response = await self._anthropic.messages.create(
                model=self.settings.anthropic_model_judge,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            text_blocks = [
                block.text
                for block in response.content
                if getattr(block, "type", None) == "text"
            ]
            aligned = "".join(text_blocks).strip()
            # Reject if LLM returned empty, much longer, or
            # completely different from the input
            if not aligned or len(aligned) > len(cleaned) * 2 + 20:
                return cleaned
            return aligned
        except Exception:
            return cleaned

    # ------------------------------------------------------------------
    # Verifier (Guard Agent pattern)
    # ------------------------------------------------------------------

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
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "revised_answer": {"type": ["string", "null"]},
                },
                "required": [
                    "is_sufficient",
                    "issues",
                    "revised_answer",
                ],
                "additionalProperties": False,
            },
            model=self.settings.anthropic_model_judge,
            max_turns=2,
        )
        return JudgeOutput.model_validate(payload)

    # ------------------------------------------------------------------
    # Agent SDK query layer
    # ------------------------------------------------------------------

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
        # Timeout: longer for tool queries, shorter for structured-only
        timeout = (
            self.settings.query_timeout_seconds
            if mcp_server is not None
            else 120
        )
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                coro = self._attempt_structured_query(
                    prompt=prompt,
                    output_schema=output_schema,
                    model=model,
                    max_turns=max_turns,
                    mcp_server=mcp_server,
                )
                return await asyncio.wait_for(coro, timeout=timeout)
            except TimeoutError:
                last_error = AgentRuntimeError(
                    f"Query timed out after {timeout}s"
                )
                if attempt == attempts:
                    break
                await asyncio.sleep(min(2**attempt, 30))
            except BaseException as exc:
                if isinstance(exc, KeyboardInterrupt | SystemExit):
                    raise
                # Unwrap ExceptionGroups (TaskGroup crashes) to get
                # the real error and allow retry
                real = _unwrap_exception_group(exc)
                last_error = _coerce_runtime_error(real)
                if attempt == attempts:
                    break
                await asyncio.sleep(min(2**attempt, 30))
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
            "Return only a valid JSON object that matches "
            "this JSON Schema exactly.\n"
            "Do not include markdown, explanations, headings, "
            "or prose outside the JSON.\n"
            f"Schema:\n{schema_text}\n"
        )
        options = ClaudeAgentOptions(
            tools=[],
            mcp_servers=(
                {MCP_SERVER_NAME: mcp_server}
                if mcp_server is not None
                else {}
            ),
            allowed_tools=(
                ALLOWED_MCP_TOOLS if mcp_server is not None else []
            ),
            system_prompt=SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            cwd=self.settings.working_directory,
            model=model,
            max_turns=max_turns,
            cli_path=self.settings.claude_cli_path,
            env=env,
            # Do NOT use output_format — it triggers a 404 from
            # the CLI's structured output endpoint. Instead, rely
            # on the JSON-extraction fallback from the prompt.
            output_format=None,
            # Extended thinking for tool-using queries
            effort="high" if mcp_server is not None else None,
        )
        result = await _collect_result(
            query(prompt=structured_prompt, options=options)
        )
        if result.structured_output is not None:
            return result.structured_output
        if result.result is None:
            raise AgentRuntimeError(
                "Claude Agent SDK returned no structured output "
                "or text result."
            )
        try:
            return _extract_json_object(result.result)
        except json.JSONDecodeError as exc:
            raise AgentRuntimeError(
                "Failed to decode Claude Agent SDK output as "
                f"JSON: {result.result}"
            ) from exc


# ------------------------------------------------------------------
# Helpers (module-level)
# ------------------------------------------------------------------


async def _collect_result(
    messages: AsyncIterator[Any],
) -> ResultMessage:
    final_result: ResultMessage | None = None
    collected_text: list[str] = []
    async for message in messages:
        if isinstance(message, ResultMessage):
            final_result = message
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    collected_text.append(block.text)
    if final_result is None:
        raise AgentRuntimeError(
            "Claude Agent SDK query completed "
            "without a ResultMessage."
        )
    if final_result.is_error:
        raise AgentRuntimeError(
            final_result.result
            or "Claude Agent SDK reported an unknown error."
        )
    # Patch in accumulated text if ResultMessage.result is empty
    if final_result.result is None and collected_text:
        final_result.result = "\n".join(collected_text)
    return final_result


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        stripped,
        flags=re.DOTALL,
    )
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


_PUNT_PHRASES = (
    "unable to determine",
    "unable to complete",
    "unable to access",
    "unable to process",
    "cannot process",
    "cannot determine",
    "unable to",
    "cannot be determined",
    "not accessible",
    "technical limitations",
    "tool failures",
)


def _is_punt_answer(answer: str | None) -> bool:
    """Check if the answer is a punt / non-answer."""
    if not answer or not answer.strip():
        return True
    lowered = answer.strip().lower()
    return any(phrase in lowered for phrase in _PUNT_PHRASES)


def _unwrap_exception_group(exc: BaseException) -> BaseException:
    """Dig into ExceptionGroup / BaseExceptionGroup to find the root cause."""
    if isinstance(exc, BaseExceptionGroup):
        # Take the first sub-exception and recurse
        if exc.exceptions:
            return _unwrap_exception_group(exc.exceptions[0])
    return exc


def _coerce_runtime_error(
    exc: BaseException,
) -> AgentRuntimeError:
    if isinstance(exc, AgentRuntimeError):
        return exc
    return AgentRuntimeError(f"{type(exc).__name__}: {exc}")


__all__ = ["AgentRuntimeError", "GaiaAgent"]
