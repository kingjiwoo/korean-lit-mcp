import hashlib
import unicodedata
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from pydantic import ValidationError
from starlette.testclient import TestClient

from korean_lit_mcp.passage_search import FindPassageRequest, find_passage
from korean_lit_mcp.runtime import create_http_app
from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import load_editions, split_paragraphs


def edition(text):
    base = load_editions(Path("data/works"))[0]
    return replace(
        base,
        text=text,
        paragraphs=split_paragraphs(text, source_lines=True),
        manifest=base.manifest.model_copy(
            update={"sha256": hashlib.sha256(text.encode()).hexdigest()}
        ),
    )


def test_repeated_overlapping_matches_and_raw_context():
    e = edition("앞\r\n하하하\r\n뒤")
    r = find_passage(
        FindPassageRequest(
            work_id=e.manifest.work_id,
            edition_id=e.manifest.edition_id,
            query="하하",
            context_chars=2,
            limit=1,
        ),
        (e,),
    )
    assert r.has_more and len(r.items) == 1
    hit = r.items[0]
    assert hit.requires_review and hit.location.paragraph_start == 2
    assert e.text[hit.location.start : hit.location.end] == hit.text == "하하"
    assert e.text[hit.context_start : hit.context_end] == hit.context_text
    assert "\r\n" in hit.context_text


def test_orthography_is_explicit_and_partial_jamo_is_not_a_match():
    e = edition(unicodedata.normalize("NFD", "한글") + "ᄃᆞ래 靑山")
    args = dict(work_id=e.manifest.work_id, edition_id=e.manifest.edition_id, query="한글")
    assert not find_passage(FindPassageRequest(**args), (e,)).items
    r = find_passage(FindPassageRequest(**args, match_mode="orthography"), (e,))
    assert r.items[0].match_kind == "orthography" and r.items[0].requires_review
    e = edition("각")
    assert not find_passage(
        FindPassageRequest(**{**args, "query": "가"}, match_mode="orthography"), (e,)
    ).items


def test_bounds_missing_edition_and_oversized_match():
    e = edition("가" + " " * 40000 + "나")
    args = dict(
        work_id=e.manifest.work_id,
        edition_id=e.manifest.edition_id,
        query="가나",
        match_mode="orthography",
    )
    r = find_passage(FindPassageRequest(**args), (e,))
    assert not r.items and r.omitted_oversized_matches == 1
    r = find_passage(FindPassageRequest(**{**args, "edition_id": "missing"}), (e,))
    assert r.error.code == "not_found" and not r.items
    for field, value in (("query", "x" * 201), ("limit", 6), ("context_chars", 301)):
        with pytest.raises(ValidationError):
            FindPassageRequest(**{**args, field: value})


async def test_mcp_phrase_search_needs_no_network_and_connects_to_verification(monkeypatch):
    async def no_network(*a, **kw):
        raise AssertionError("Phrase search must stay local")

    monkeypatch.setattr(httpx.AsyncClient, "send", no_network)
    es = load_editions(Path("data/works"))
    e = next(e for e in es if e.manifest.title == "청산별곡")
    async with Client(create_server(editions=es)) as client:
        r = (
            await client.call_tool(
                "find_passage",
                {
                    "request": {
                        "work_id": e.manifest.work_id,
                        "edition_id": e.manifest.edition_id,
                        "query": "멀위랑 ᄃᆞ래랑",
                    }
                },
            )
        ).structured_content
        assert r["items"]
        hit = r["items"][0]
        checked = (
            await client.call_tool(
                "verify_quote",
                {
                    "request": {
                        "work_id": r["work_id"],
                        "edition_id": r["edition_id"],
                        "source_hash": r["source_hash"],
                        "quotes": [hit["text"]],
                    }
                },
            )
        ).structured_content
        assert checked["items"][0]["status"] == "exact"


@pytest.mark.parametrize("mode", ["exact", "orthography"])
def test_default_http_phrase_search_budget(mode):
    e = edition(("가" * 200 + "\n") * 20 if mode == "exact" else "가\u3000\u3000" * 300)
    with TestClient(
        create_http_app(editions=(e,), allowed_hosts=["localhost"]), base_url="http://localhost"
    ) as c:
        r = c.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "find_passage",
                    "arguments": {
                        "request": {
                            "work_id": e.manifest.work_id,
                            "edition_id": e.manifest.edition_id,
                            "query": "가" * 200,
                            "match_mode": mode,
                        }
                    },
                },
            },
        )
        assert r.status_code == 200 and len(r.content) <= 16 * 1024
        assert r.json()["result"]["structuredContent"]["has_more"]
