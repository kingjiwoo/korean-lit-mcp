"""Content-free tool metrics; never serialize arguments, results or exceptions."""

import logging
import time
from contextvars import ContextVar

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from mcp.types import CallToolRequestParams

request_id: ContextVar[str] = ContextVar("request_id", default="local")


class ToolMetrics(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        name = context.message.name
        if name not in {
            "search_works",
            "get_passage",
            "verify_quote",
            "search_classical_text",
            "lookup_grammar",
        }:
            name = "unknown"
        started = time.monotonic()
        outcome = "exception"
        try:
            result = await call_next(context)
            data = result.structured_content
            outcome = "domain_error" if isinstance(data, dict) and data.get("error") else "ok"
            return result
        finally:
            logging.getLogger(__name__).info(
                "tool request_id=%s name=%s outcome=%s elapsed_ms=%d",
                request_id.get(),
                name,
                outcome,
                int((time.monotonic() - started) * 1000),
            )
