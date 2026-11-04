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


async def test_classical_corpus_editions_and_attribution():
    editions = load_editions(Path("data/works"))
    async with Client(create_server(editions=editions)) as client:
        for title in ("사미인곡", "청산별곡", "관동별곡", "규원가", "홍길동전"):
            data = (
                await client.call_tool("search_works", {"request": {"query": title}})
            ).structured_content
            supplied = [i for i in data["items"] if i["available_text"]]
            assert supplied
            if title == "관동별곡":
                assert any(i["author"] == "안축" and not i["available_text"] for i in data["items"])
            for selected in supplied:
                ids = {k: selected[k] for k in ("work_id", "edition_id")}
                edition = next(e for e in editions if e.manifest.edition_id == ids["edition_id"])
                assert "".join(p.text for p in edition.paragraphs) == edition.text
                quote = next(p.text for p in edition.paragraphs if p.text.strip())[:100]
                request = {**ids, "source_hash": edition.manifest.sha256, "quotes": [quote]}
                result = (
                    await client.call_tool("verify_quote", {"request": request})
                ).structured_content
                assert result["error"] is None and result["items"][0]["status"] == "exact"
                if title == "청산별곡":
                    assert result["copyright"] == "licensed"
                    assert "한국민족문화대백과사전" in result["source"]["name"]
        ambiguous = (
            await client.call_tool(
                "get_passage", {"request": {"work_id": "classical-honggildongjeon"}}
            )
        ).structured_content
        assert ambiguous["error"]["code"] == "ambiguous_edition"
        unavailable = (
            await client.call_tool("search_works", {"request": {"query": "구운몽"}})
        ).structured_content
        assert all(not i["available_text"] for i in unavailable["items"])


async def test_one_result_keeps_supplied_rights_without_hidden_discovery():
    async with Client(create_server(editions=load_editions(Path("data/works")))) as client:
        result = (
            await client.call_tool("search_works", {"request": {"query": "관동별곡", "limit": 1}})
        ).structured_content
    assert result["copyright"] == "public_domain"
    assert len(result["items"]) == 1 and result["items"][0]["available_text"]
    assert "미확보 후보" not in result["note"]
