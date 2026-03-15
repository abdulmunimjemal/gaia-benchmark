from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from gaia_bot.agent.constants import ALLOWED_MCP_TOOLS, MCP_SERVER_NAME, MCP_SERVER_VERSION
from gaia_bot.config.settings import Settings
from gaia_bot.contracts.basemodels import SearchHit, ToolTrace
from gaia_bot.services.artifacts import TaskArtifactManager


class SandboxRuntime:
    def __init__(self, settings: Settings, artifact_manager: TaskArtifactManager) -> None:
        self.settings = settings
        self.artifact_manager = artifact_manager
        self.trace: list[ToolTrace] = []
        self._executor = None

    async def __aenter__(self) -> SandboxRuntime:
        from gaia_bot.services.executor import SandboxExecutor

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
            from gaia_bot.services.research import WebResearchClient

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
            from gaia_bot.services.research import WebResearchClient

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
            from gaia_bot.services.research import WebResearchClient

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
            name=MCP_SERVER_NAME,
            version=MCP_SERVER_VERSION,
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


__all__ = ["ALLOWED_MCP_TOOLS", "SandboxRuntime"]
