import hashlib
from pathlib import Path

from fastmcp import Client

from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import load_editions


async def test_sami_alias_to_original_and_corrected_quote():
    editions = load_editions(Path("data/works"))
    edition = next(e for e in editions if e.manifest.work_id == "gongu-13313606")
    assert len(edition.paragraphs) == 65
    assert edition.text.startswith("\r\n\r\n")
    assert "이 몸이 태어날 때" not in edition.text
    assert hashlib.sha256(edition.text.encode()).hexdigest() == (
        "04082bb8aae54121d5bbb61e20fa24f521a6c1f968700255a9dc9fce8aefc0b1"
    )
    async with Client(create_server(editions=editions)) as client:
        found = (
            await client.call_tool("search_works", {"request": {"query": "思美人曲"}})
        ).structured_content
        selected = found["items"][0]
        assert selected["available_text"]
        ids = {k: selected[k] for k in ("work_id", "edition_id")}
        passage = (
            await client.call_tool("get_passage", {"request": {**ids, "start": 3, "end": 4}})
        ).structured_content
        item = passage["items"][0]
        quote = item["paragraphs"][0]["text"]
        assert quote == edition.paragraphs[2].text
        request = {**ids, "source_hash": item["source_hash"], "quotes": [quote]}
        result = (await client.call_tool("verify_quote", {"request": request})).structured_content
        assert result["items"][0]["status"] == "exact"
        request["quotes"] = [quote.replace(" ", "  ") if " " in quote else quote.rstrip() + " "]
        changed = (await client.call_tool("verify_quote", {"request": request})).structured_content
        assert changed["items"][0]["status"] != "exact"
        assert changed["items"][0]["requires_review"]
        request["quotes"] = [quote]
        repaired = (await client.call_tool("verify_quote", {"request": request})).structured_content
        assert repaired["items"][0]["status"] == "exact"
        stale = (
            await client.call_tool(
                "verify_quote", {"request": {**request, "source_hash": "0" * 64}}
            )
        ).structured_content
        assert stale["error"]["code"] == "source_changed"


def test_discovery_does_not_label_supplied_work_unavailable():
    from korean_lit_mcp.contracts import SearchRequest
    from korean_lit_mcp.discovery import discover_work

    result = discover_work(SearchRequest(query="思美人曲"), load_editions(Path("data/works")))
    assert result is None
