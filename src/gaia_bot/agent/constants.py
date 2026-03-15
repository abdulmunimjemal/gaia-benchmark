"""Constants used by the agent runtime."""

MCP_SERVER_NAME = "gaia"
MCP_SERVER_VERSION = "0.2.0"
ALLOWED_MCP_TOOLS = [
    "mcp__gaia__research_topic",
    "mcp__gaia__web_search",
    "mcp__gaia__fetch_url",
    "mcp__gaia__read_task_attachment",
    "mcp__gaia__read_local_file",
    "mcp__gaia__sandbox_exec",
]

__all__ = ["ALLOWED_MCP_TOOLS", "MCP_SERVER_NAME", "MCP_SERVER_VERSION"]
