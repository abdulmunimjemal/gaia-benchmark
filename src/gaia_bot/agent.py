from __future__ import annotations

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
    create_sdk_mcp_server,
    query,
    tool,
)
from tenacity import retry, stop_after_attempt, wait_fixed

from gaia_bot.artifacts import TaskArtifactManager
from gaia_bot.models import (
    JudgeOutput,
    PlannerDecision,
    SearchHit,
    SolverOutput,
    TaskRecord,
    TaskRunResult,
    ToolTrace,
)
from gaia_bot.prompts import (
    SYSTEM_PROMPT,
    direct_prompt,
    route_prompt,
    solver_prompt,
    verifier_prompt,
)
from gaia_bot.router import heuristic_route
from gaia_bot.scoring import classify_failure, format_benchmark_answer, score_prediction
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
        tool_calls: list[ToolTrace] = []

        if (
            planner.route == "direct"
            and planner.risk == "low"
            and not planner.use_verifier
            and not planner.needs_artifact
            and not planner.needs_web
            and not planner.needs_code
        ):
            solver = await self._solve_direct(task, planner)
            final_answer = format_benchmark_answer(solver.answer, planner.answer_shape)
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
                final_answer = format_benchmark_answer(solver.answer, planner.answer_shape)
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
                        )
                        judge = await self._verify(task, planner, solver)
                tool_calls = runtime.trace

        final_answer = format_benchmark_answer(
            judge.revised_answer or final_answer,
            planner.answer_shape,
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
        schema_text = json.dumps(output_schema, indent=2)
        structured_prompt = (
            f"{prompt}\n\n"
            "Return only a valid JSON object that matches this JSON Schema exactly.\n"
            "Do not include markdown, explanations, headings, or prose outside the JSON.\n"
            f"Schema:\n{schema_text}\n"
        )
        options = ClaudeAgentOptions(
            tools=[],
            mcp_servers={"gaia": mcp_server} if mcp_server is not None else {},
            allowed_tools=(
                [
                    "mcp__gaia__research_topic",
                    "mcp__gaia__web_search",
                    "mcp__gaia__fetch_url",
                    "mcp__gaia__read_task_attachment",
                    "mcp__gaia__read_local_file",
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
        result = await _collect_result(query(prompt=structured_prompt, options=options))
        if result.structured_output is None:
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


class SandboxRuntime:
    def __init__(self, settings: Settings, artifact_manager: TaskArtifactManager) -> None:
        self.settings = settings
        self.artifact_manager = artifact_manager
        self.trace: list[ToolTrace] = []
        self._executor = None

    async def __aenter__(self) -> SandboxRuntime:
        from gaia_bot.executor import SandboxExecutor

        self._executor = SandboxExecutor(self.settings)
        await self._executor.ensure_started()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        if self._executor is not None:
            await self._executor.close()

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
            from gaia_bot.research import WebResearchClient

            query_text = args["query"]
            max_results = int(args.get("max_results", runtime.settings.max_search_results))
            research = WebResearchClient(runtime.settings)
            hits = await research.search(query_text, max_results=max_results)
            runtime._record_tool(
                "web_search",
                "research",
                args,
                _summarize_search_hits(hits),
            )
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
            await runtime.artifact_manager.persist_web_extract(args["url"], text)
            runtime._record_tool("fetch_url", "research", args, text[:400])
            return {"content": [{"type": "text", "text": text}]}

        @tool(
            "research_topic",
            "Search broadly, fetch top sources, and return a compact research brief.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        )
        async def research_topic_tool(args: dict[str, Any]) -> dict[str, Any]:
            from gaia_bot.research import WebResearchClient

            query_text = args["query"]
            max_results = int(args.get("max_results", 3))
            research = WebResearchClient(runtime.settings)
            hits = await research.search(query_text, max_results=max_results)
            sections = []
            for hit in hits[:3]:
                extracted = await research.fetch(hit.url, max_chars=3000)
                await runtime.artifact_manager.persist_web_extract(hit.url, extracted)
                sections.append(
                    
                        f"Title: {hit.title}\n"
                        f"URL: {hit.url}\n"
                        f"Snippet: {hit.snippet}\n"
                        f"Extract:\n{extracted[:1400]}"
                    
                )
            summary = "\n\n---\n\n".join(sections) or "No results"
            runtime._record_tool("research_topic", "research", args, summary[:400])
            return {"content": [{"type": "text", "text": summary}]}

        @tool(
            "read_task_attachment",
            "Read and extract text from the current task attachment, if one exists.",
            {"type": "object", "properties": {}, "additionalProperties": False},
        )
        async def read_task_attachment_tool(_args: dict[str, Any]) -> dict[str, Any]:
            observation = await runtime.artifact_manager.read_task_attachment()
            if observation is None:
                runtime._record_tool(
                    "read_task_attachment",
                    "artifact",
                    {},
                    "No attachment available for this task.",
                    success=False,
                )
                return {"content": [{"type": "text", "text": "No attachment available."}]}
            text = Path(observation.stored_path).read_text()
            runtime._record_tool(
                "read_task_attachment",
                "artifact",
                {},
                observation.excerpt,
            )
            return {"content": [{"type": "text", "text": text}]}

        @tool(
            "read_local_file",
            "Read and extract text from a local file path. Use for files created during analysis.",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        )
        async def read_local_file_tool(args: dict[str, Any]) -> dict[str, Any]:
            path = Path(args["path"])
            observation = await runtime.artifact_manager.read_local_path(path)
            text = Path(observation.stored_path).read_text()
            runtime._record_tool("read_local_file", "artifact", args, observation.excerpt)
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
            assert runtime._executor is not None
            result = await runtime._executor.execute(
                args["code"],
                language=args.get("language", "python"),
                timeout=args.get("timeout"),
            )
            runtime._record_tool(
                "sandbox_exec",
                "code",
                args,
                _summarize_execution(result),
                success=result.ok,
            )
            return {"content": [{"type": "text", "text": result.model_dump_json(indent=2)}]}

        return create_sdk_mcp_server(
            name="gaia",
            version="0.2.0",
            tools=[
                web_search_tool,
                fetch_url_tool,
                research_topic_tool,
                read_task_attachment_tool,
                read_local_file_tool,
                sandbox_exec_tool,
            ],
        )

    def _record_tool(
        self,
        name: str,
        category: str,
        arguments: dict[str, Any],
        summary: str,
        *,
        success: bool = True,
    ) -> None:
        self.trace.append(
            ToolTrace(
                name=name,
                category=category,
                arguments=arguments,
                summary=summary,
                success=success,
            )
        )


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
