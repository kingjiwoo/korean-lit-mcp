from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from korean_lit_mcp.contracts import Envelope, PassageRequest, Source
from korean_lit_mcp.grammar import load_grammar
from korean_lit_mcp.server import create_server


async def test_mcp_round_trip() -> None:
    server = create_server()

    @server.tool
    def sample(request: PassageRequest) -> Envelope[str]:
        return Envelope(items=[request.work_id or request.title or ""], source=Source(name="test"))

    @server.tool
    def failure() -> str:
        raise RuntimeError("private_marker_not_for_client")

    async with Client(server) as client:
        tools = await client.list_tools()
        assert "sample" in [tool.name for tool in tools]
        result = await client.call_tool("sample", {"request": {"work_id": "test"}})
        assert result.structured_content is not None
        assert result.structured_content["items"] == ["test"]
        with pytest.raises(ToolError):
            await client.call_tool("sample", {"request": {}})
        with pytest.raises(ToolError) as error:
            await client.call_tool("failure", {})
        assert "private_marker" not in str(error.value)


async def test_grammar_mcp_needs_no_model_or_upstream(monkeypatch) -> None:
    async def no_network(*args, **kwargs):
        raise AssertionError("Grammar lookup must not call an external service.")

    monkeypatch.setattr(httpx.AsyncClient, "send", no_network)
    server = create_server(grammar_entries=load_grammar(Path("data/grammar")))
    async with Client(server) as client:
        tool = next(t for t in await client.list_tools() if t.name == "lookup_grammar")
        assert tool.annotations is not None and tool.annotations.read_only_hint
        result = await client.call_tool(
            "lookup_grammar", {"request": {"term": "수록하지않은문법용어", "period": "modern"}}
        )
        assert result.structured_content is not None
        assert result.structured_content["items"] == []
        found = await client.call_tool(
            "lookup_grammar", {"request": {"term": "어간", "period": "modern"}}
        )
        assert found.structured_content is not None
        assert found.structured_content["items"][0]["entry_id"] == "modern-stem"
