import os

import httpx
import pytest
from fastmcp import Client

URL = os.getenv("TEST_MCP_URL")
TOKEN = os.getenv("TEST_MCP_TOKEN")
pytestmark = pytest.mark.skipif(not URL or not TOKEN, reason="Set TEST_MCP_URL and TEST_MCP_TOKEN")


async def test_live_http_workflow() -> None:
    assert URL and TOKEN
    async with httpx.AsyncClient() as http:
        assert (await http.get(URL.rstrip("/").removesuffix("/mcp") + "/health")).status_code == 200
        assert (await http.post(URL)).status_code == 401
        legacy = await http.post(
            URL,
            headers={
                "Authorization": "Bearer " + TOKEN,
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
    async with Client(URL, auth=TOKEN) as client:
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
