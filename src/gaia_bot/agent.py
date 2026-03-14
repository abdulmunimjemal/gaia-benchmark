from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)
from tenacity import retry, stop_after_attempt, wait_fixed

from gaia_bot.benchmark import score_prediction
from gaia_bot.executor import SandboxExecutor
from gaia_bot.models import (
    JudgeOutput,
    PlannerDecision,
    SearchHit,
    SolverOutput,
    TaskRecord,
    TaskRunResult,
    ToolTrace,
)
from gaia_bot.prompts import SYSTEM_PROMPT, judge_prompt, planner_prompt, solver_prompt
from gaia_bot.settings import Settings


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
        self._anthropic = AsyncAnthropic(
            api_key=api_key,
        )

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

    async def solve(self, task: TaskRecord, *, run_id: str) -> TaskRunResult:
        self.settings.require_service_credentials(require_anthropic=True, require_e2b=True)
        started_at = time.perf_counter()

        planner = await self._plan(task)
        async with SandboxExecutor(self.settings) as executor:
            runtime = AgentToolRuntime(executor=executor, settings=self.settings)
            solver = await self._solve_with_runtime(task, planner, runtime)
            judge = await self._judge(task, solver)
            if not judge.is_sufficient and judge.issues:
                solver = await self._solve_with_runtime(
                    task,
                    planner,
                    runtime,
                    critique=judge.issues,
                )
                judge = await self._judge(task, solver)

        score = score_prediction(solver.answer, task.expected_answer)
        duration_seconds = time.perf_counter() - started_at
        return TaskRunResult(
            run_id=run_id,
            task_id=task.task_id,
            question=task.question,
            answer=judge.revised_answer or solver.answer,
            expected_answer=task.expected_answer,
            score=score,
            passed=(score == 1.0) if score is not None else None,
            planner=planner,
            solver=solver,
            judge=judge,
            tool_calls=runtime.trace,
            duration_seconds=duration_seconds,
            metadata=task.metadata,
        )

    async def _plan(self, task: TaskRecord) -> PlannerDecision:
        payload = await self._run_structured_query(
            prompt=planner_prompt(task),
            output_schema={
                "type": "object",
                "properties": {
                    "needs_web": {"type": "boolean"},
                    "needs_code": {"type": "boolean"},
                    "research_queries": {"type": "array", "items": {"type": "string"}},
                    "working_plan": {"type": "array", "items": {"type": "string"}},
                    "answer_shape": {"type": "string"},
                },
                "required": [
                    "needs_web",
                    "needs_code",
                    "research_queries",
                    "working_plan",
                    "answer_shape",
                ],
                "additionalProperties": False,
            },
            model=self.settings.anthropic_model_judge,
            max_turns=2,
        )
        return PlannerDecision.model_validate(payload)

    async def _solve_with_runtime(
        self,
        task: TaskRecord,
        planner: PlannerDecision,
        runtime: AgentToolRuntime,
        *,
        critique: list[str] | None = None,
    ) -> SolverOutput:
        server = runtime.create_mcp_server()
        payload = await self._run_structured_query(
            prompt=solver_prompt(task, planner, critique),
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

    async def _judge(self, task: TaskRecord, solver: SolverOutput) -> JudgeOutput:
        payload = await self._run_structured_query(
            prompt=judge_prompt(task, solver.answer, solver.citations),
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

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
    async def _run_structured_query(
        self,
        *,
        prompt: str,
        output_schema: dict[str, Any],
        model: str,
        max_turns: int,
        mcp_server: Any | None = None,
    ) -> dict[str, Any]:
        env = self.settings.runtime_env()
        options = ClaudeAgentOptions(
            tools=[],
            mcp_servers={"gaia": mcp_server} if mcp_server is not None else {},
            allowed_tools=(
                [
                    "mcp__gaia__web_search",
                    "mcp__gaia__fetch_url",
                    "mcp__gaia__sandbox_exec",
                ]
                if mcp_server is not None
                else []
            ),
            system_prompt=SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            cwd=self.settings.working_directory,
            model=model,
            max_turns=max_turns,
            cli_path=self.settings.claude_cli_path,
            env=env,
            output_format=output_schema,
        )
        result = await _collect_result(query(prompt=prompt, options=options))
        if result.structured_output is None:
            if result.result is None:
                raise AgentRuntimeError(
                    "Claude Agent SDK returned no structured output or text result."
                )
            try:
                return json.loads(result.result)
            except json.JSONDecodeError as exc:
                raise AgentRuntimeError(
                    f"Failed to decode Claude Agent SDK output as JSON: {result.result}"
                ) from exc
        return result.structured_output


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


class AgentToolRuntime:
    def __init__(self, *, executor: SandboxExecutor, settings: Settings) -> None:
        self.executor = executor
        self.settings = settings
        self.trace: list[ToolTrace] = []

    def create_mcp_server(self) -> Any:
        runtime = self

        @tool(
            "web_search",
            "Search the public web for relevant sources and return titles, urls, and snippets.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        )
        async def web_search_tool(args: dict[str, Any]) -> dict[str, Any]:
            query_text = args["query"]
            max_results = int(args.get("max_results", runtime.settings.max_search_results))
            from gaia_bot.research import WebResearchClient

            research = WebResearchClient(runtime.settings)
            hits = await research.search(query_text, max_results=max_results)
            runtime._record_tool("web_search", args, _summarize_search_hits(hits))
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps([hit.model_dump() for hit in hits]),
                    }
                ]
            }

        @tool(
            "fetch_url",
            "Fetch and extract text from a URL, including HTML pages and PDFs.",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "max_chars": {"type": "integer", "minimum": 500},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        )
        async def fetch_url_tool(args: dict[str, Any]) -> dict[str, Any]:
            from gaia_bot.research import WebResearchClient

            research = WebResearchClient(runtime.settings)
            text = await research.fetch(args["url"], max_chars=args.get("max_chars"))
            runtime._record_tool("fetch_url", args, text[:400])
            return {"content": [{"type": "text", "text": text}]}

        @tool(
            "sandbox_exec",
            (
                "Execute code inside the E2B sandbox. "
                "Use this for calculations, parsing, and reproducible transforms."
            ),
            {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "language": {"type": "string"},
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 300},
                },
                "required": ["code"],
                "additionalProperties": False,
            },
        )
        async def sandbox_exec_tool(args: dict[str, Any]) -> dict[str, Any]:
            result = await runtime.executor.execute(
                args["code"],
                language=args.get("language", "python"),
                timeout=args.get("timeout"),
            )
            runtime._record_tool("sandbox_exec", args, _summarize_execution(result))
            return {"content": [{"type": "text", "text": result.model_dump_json(indent=2)}]}

        return create_sdk_mcp_server(
            name="gaia",
            version="0.1.0",
            tools=[web_search_tool, fetch_url_tool, sandbox_exec_tool],
        )

    def _record_tool(self, name: str, arguments: dict[str, Any], summary: str) -> None:
        self.trace.append(ToolTrace(name=name, arguments=arguments, summary=summary))


def _summarize_search_hits(hits: list[SearchHit]) -> str:
    if not hits:
        return "No results returned."
    return " | ".join(f"{hit.title}: {hit.url}" for hit in hits[:3])


def _summarize_execution(result: Any) -> str:
    pieces = []
    if result.stdout:
        pieces.append(f"stdout={result.stdout[:160]}")
    if result.stderr:
        pieces.append(f"stderr={result.stderr[:160]}")
    if result.results:
        pieces.append(f"results={result.results[0][:160]}")
    if result.error_name:
        pieces.append(f"error={result.error_name}: {result.error_value}")
    return " | ".join(pieces) or "Execution completed with no output."
