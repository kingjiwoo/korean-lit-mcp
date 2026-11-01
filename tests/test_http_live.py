import os

import httpx
import pytest
from fastmcp import Client

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
