import os

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

URL = os.getenv("TEST_MCP_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Set TEST_MCP_URL")


async def test_live_http_workflow() -> None:
    assert URL
    async with httpx.AsyncClient() as http:
        assert (await http.get(URL.rstrip("/").removesuffix("/mcp") + "/health")).status_code == 200
        legacy = await http.post(
            URL,
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Protocol-Version": "2025-11-25",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "compatibility-check", "version": "1"},
                },
            },
        )
        assert legacy.status_code == 200
        assert legacy.json()["result"]["protocolVersion"] == "2025-11-25"
    async with Client(URL) as client:
        assert {tool.name for tool in await client.list_tools()} == {
            "search_works",
            "search_classical_text",
            "get_passage",
            "verify_quote",
            "lookup_grammar",
        }
        result = await client.call_tool(
            "get_passage", {"request": {"work_id": "gongu-9000397", "start": 2, "end": 2}}
        )
        assert result.structured_content is not None
        passage = result.structured_content["items"][0]
        text = passage["paragraphs"][0]["text"]
        verified = await client.call_tool(
            "verify_quote",
            {
                "request": {
                    "quotes": [text],
                    "work_id": passage["work_id"],
                    "edition_id": passage["edition_id"],
                    "source_hash": passage["source_hash"],
                }
            },
        )
        assert verified.structured_content["all_submitted_exact"]
        for term, period, entry_id in (
            ("주격조사", "modern", "modern-subject-particle"),
            ("히읗종성체언", "middle", "middle-h-final-noun"),
            ("거듭적기", "early_modern", "early-modern-double-spelling"),
        ):
            grammar = await client.call_tool(
                "lookup_grammar", {"request": {"term": term, "period": period}}
            )
            assert grammar.structured_content is not None
            item = grammar.structured_content["items"][0]
            assert item["entry_id"] == entry_id and item["period"] == period
            assert item["sources"][0]["license"] == "CC-BY-SA-2.0-KR"
            if period == "early_modern":
                assert item["examples"][0]["text"] == "말이 → 말미"
        missing = await client.call_tool(
            "lookup_grammar", {"request": {"term": "수록되지않은문법개념", "period": "middle"}}
        )
        assert missing.structured_content is not None
        assert missing.structured_content["items"] == []
        assert missing.structured_content["error"] is None
        with pytest.raises(ToolError):
            await client.call_tool(
                "lookup_grammar", {"request": {"term": "어간", "period": "modern", "limit": 11}}
            )
