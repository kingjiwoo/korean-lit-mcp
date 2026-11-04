import json
from pathlib import Path

import pytest
from fastmcp import Client
from starlette.testclient import TestClient

from korean_lit_mcp.catalogue import NationalLibrary
from korean_lit_mcp.contracts import Envelope, Source
from korean_lit_mcp.runtime import create_http_app
from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import load_editions


@pytest.mark.parametrize(
    "query", ["사미인곡", "청산별곡", "관동별곡", "규원가", "구운몽", "홍길동전"]
)
async def test_default_known_work_never_dumps_music(monkeypatch, query):
    async def unexpected(*args):
        raise AssertionError("Discovery should not make an unbounded catalogue call")

    monkeypatch.setattr(NationalLibrary, "search", unexpected)
    async with Client(create_server(nl_api_key="fixture-key")) as client:
        result = await client.call_tool("search_works", {"request": {"query": query}})
    data = result.structured_content
    assert data["search_context"]["outcome"] == "work_identified"
    assert 1 <= len(data["items"]) <= 3
    for item in data["items"]:
        assert item["kind"] == "work_candidate" and not item["available_text"]
        assert "work_id" not in item
        assert item["text_status"] == "unavailable" and item["next_searches"]
    if query == "관동별곡":
        assert {i["author"] for i in data["items"]} == {"정철", "안축"}


async def test_author_filter_and_reviewed_text_priority():
    async with Client(create_server(editions=load_editions(Path("data/works")))) as client:
        known = await client.call_tool(
            "search_works", {"request": {"query": "관동별곡", "author": "정철"}}
        )
        assert [i["author"] for i in known.structured_content["items"]] == ["정철"]
        modern = await client.call_tool("search_works", {"request": {"query": "김유정"}})
        assert len(modern.structured_content["items"]) == 2
        assert all(
            i["kind"] == "reviewed_edition" and i["available_text"]
            for i in modern.structured_content["items"]
        )


async def test_explicit_catalogue_retains_music_but_literature_excludes_it(monkeypatch):
    async def metadata(self, request):
        return Envelope(
            source=Source(name="합성 기관"),
            items=[
                {"title": "합성 노래", "material_type": "음악자료", "available_text": False},
                {
                    "title": "합성 소설",
                    "material_type": "도서",
                    "kdc": "8",
                    "available_text": False,
                },
                {
                    "title": "음악 악보",
                    "material_type": "도서",
                    "kdc": "6",
                    "available_text": False,
                },
            ],
        )

    monkeypatch.setattr(NationalLibrary, "search", metadata)
    async with Client(create_server(nl_api_key="fixture-key")) as client:
        literary = await client.call_tool("search_works", {"request": {"query": "합성"}})
        assert [i["title"] for i in literary.structured_content["items"]] == ["합성 소설"]
        assert literary.structured_content["search_context"]["outcome"] == "related_records"
        raw = await client.call_tool(
            "search_works", {"request": {"query": "합성", "mode": "catalogue"}}
        )
        assert len(raw.structured_content["items"]) == 3


def test_default_http_response_budget():
    app = create_http_app(editions=(), allowed_hosts=["localhost"])
    with TestClient(app, base_url="http://localhost") as client:
        for title in ("사미인곡", "청산별곡", "관동별곡"):
            result = client.post(
                "/mcp",
                headers={"Accept": "application/json, text/event-stream"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "search_works", "arguments": {"request": {"query": title}}},
                },
            )
            assert result.status_code == 200
            assert len(result.content) <= 16 * 1024
            assert result.json()["result"]["structuredContent"]["items"]


def test_summary_keeps_access_notes_or_reports_omission():
    from korean_lit_mcp.discovery import summarize_bibliography

    item = {
        "title": "합성" * 300,
        "author": "합성" * 150,
        "material_type": "도서",
        "available_text": False,
        "access_note": "권리 확인",
    }
    summaries, omitted = summarize_bibliography([item])
    assert summaries[0]["summary_truncated"] and summaries[0]["access_note"] == "권리 확인"
    assert omitted == 0
    _, omitted = summarize_bibliography([{**item, "access_note": "긴 조건" * 2000}])
    assert omitted == 1
    assert len(json.dumps(summaries, ensure_ascii=False).encode()) < 1800


async def test_unknown_author_filter_is_not_confirmed():
    async with Client(create_server()) as client:
        result = await client.call_tool(
            "search_works", {"request": {"query": "규원가", "author": "합성 작가"}}
        )
    item = result.structured_content["items"][0]
    assert item["author"] is None and item["author_filter_status"] == "unconfirmed"
