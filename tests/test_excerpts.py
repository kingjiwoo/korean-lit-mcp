from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from pydantic import ValidationError

from korean_lit_mcp.contracts import VerifyRequest
from korean_lit_mcp.excerpts import ExcerptRequest, verify_excerpt
from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import load_editions
from korean_lit_mcp.verification import verify_quote


def check(source, quote, **rules):
    return verify_excerpt(
        ExcerptRequest(
            source_text=source,
            segments=[{"start": 0, "end": len(source), "quote": quote}],
            rules=rules,
        )
    )


def test_explicit_edits_keep_source_offsets_and_strict_verification():
    source = "서른[5] 말ᄉᆞᆷ\r\n"
    quote = "서른 말ᄉᆞᆷ"
    assert check(source, quote).items[0].status == "mismatch"
    result = check(source, quote, drop_note_markers=["[5]"], ignore_whitespace=True)
    hit = result.items[0]
    assert result.all_match_rules and not result.all_raw_exact
    assert hit.status == "edited_match" and hit.requires_review
    assert hit.original == source
    assert "".join(source[i] for i in hit.source_comparison.positions) == hit.source_comparison.text
    assert any(r.text == "[5]" for r in hit.source_comparison.removed)
    assert (
        verify_quote(VerifyRequest(source_text=source, quotes=[quote])).items[0].status != "exact"
    )


@pytest.mark.parametrize(
    "source,quote,rules",
    [
        ("[5]", "[6]", {"drop_note_markers": ["[5]", "[6]"]}),
        ("간다.", "안 간다.", {"ignore_whitespace": True}),
        ("ᄃᆞ래 靑山", "다래 青山", {"ignore_whitespace": True}),
        ("주석[5]", "주석", {"drop_note_markers": ["[6]"]}),
    ],
)
def test_edits_do_not_hide_undeclared_or_lexical_changes(source, quote, rules):
    result = check(source, quote, **rules)
    assert result.items[0].status == "mismatch"
    assert result.items[0].requires_review and not result.all_match_rules


def test_exact_and_ordered_omissions():
    source = "처음\r\n생략할 중간\r\n마지막"
    end_start = source.index("마지막")
    request = ExcerptRequest(
        source_text=source,
        segments=[
            {"start": 0, "end": 2, "quote": "처음"},
            {"start": end_start, "end": len(source), "quote": "마지막"},
        ],
    )
    result = verify_excerpt(request)
    assert result.all_raw_exact and result.all_match_rules
    assert source[result.omissions[0].start : result.omissions[0].end] == "\r\n생략할 중간\r\n"
    with pytest.raises(ValidationError):
        ExcerptRequest(**{**request.model_dump(), "segments": list(reversed(request.segments))})


def test_invalid_ranges_rules_and_totals():
    for changes in ({"start": 2, "end": 1}, {"end": 4001}):
        with pytest.raises(ValidationError):
            ExcerptRequest(
                source_text="합성", segments=[{"start": 0, "end": 2, "quote": "합성", **changes}]
            )
    for rules in ({"drop_note_markers": [".*"]}, {"drop_note_markers": ["[5]", "[5]"]}):
        with pytest.raises(ValidationError):
            ExcerptRequest(
                source_text="합성", segments=[{"start": 0, "end": 2, "quote": "합성"}], rules=rules
            )
    result = verify_excerpt(
        ExcerptRequest(source_text="합성", segments=[{"start": 1, "end": 3, "quote": "합성"}])
    )
    assert result.error.code == "invalid_range" and not result.items


def test_change_details_are_bounded_and_not_silently_lost():
    r = check("가[5]" * 100, "가" * 100, drop_note_markers=["[5]"])
    edits = r.items[0].source_comparison
    assert r.all_match_rules and len(edits.removed) == 20
    assert edits.changes_truncated and edits.removed_count == 100


async def test_mcp_edits_stay_local_private_and_check_edition_hash(monkeypatch, caplog):
    async def no_network(*a, **kw):
        raise AssertionError("Excerpt verification must stay local")

    monkeypatch.setattr(httpx.AsyncClient, "send", no_network)
    es = load_editions(Path("data/works"))
    e = next(e for e in es if e.manifest.title == "규원가")
    line = e.paragraphs[2]
    async with Client(create_server(editions=es)) as c:
        args = {
            "work_id": e.manifest.work_id,
            "edition_id": e.manifest.edition_id,
            "source_hash": e.manifest.sha256,
            "segments": [
                {"start": line.start, "end": line.end, "quote": line.text.replace("[5]", "")}
            ],
            "rules": {"drop_note_markers": ["[5]"]},
        }
        r = (await c.call_tool("verify_excerpt", {"request": args})).structured_content
        assert r["items"][0]["status"] == "edited_match"
        stale = (
            await c.call_tool("verify_excerpt", {"request": {**args, "source_hash": "0" * 64}})
        ).structured_content
        assert stale["error"]["code"] == "source_changed" and not stale["items"]
        private = "비공개 합성 본문 ᄃᆞ래[5]"
        r = (
            await c.call_tool(
                "verify_excerpt",
                {
                    "request": {
                        "source_text": private,
                        "segments": [{"start": 0, "end": len(private), "quote": private}],
                    }
                },
            )
        ).structured_content
        assert r["all_raw_exact"]
        assert private not in caplog.text


def test_many_differences_have_explicit_truncation():
    source = "".join(chr(0x4E00 + i) for i in range(100))
    quote = "".join(c if i % 2 else chr(0x6000 + i) for i, c in enumerate(source))
    hit = check(source, quote).items[0]
    assert hit.status == "mismatch" and len(hit.differences) == 20
    assert hit.differences_count == 50 and hit.differences_truncated


def test_bounded_http_excerpt_result():
    from starlette.testclient import TestClient

    from korean_lit_mcp.runtime import create_http_app

    source = "".join(chr(0x20000 + i) for i in range(10000))
    segments = [
        {
            "start": start,
            "end": start + 2000,
            "quote": "".join(chr(0x30000 + i) for i in range(start, start + 2000)),
        }
        for start in range(0, 10000, 2000)
    ]
    with TestClient(
        create_http_app(editions=(), allowed_hosts=["localhost"]), base_url="http://localhost"
    ) as c:
        r = c.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "verify_excerpt",
                    "arguments": {"request": {"source_text": source, "segments": segments}},
                },
            },
        )
        assert r.status_code == 200 and len(r.content) < 1024 * 1024
        assert len(r.json()["result"]["structuredContent"]["items"]) == 5


def test_raw_exact_is_independent_of_edits_and_gaps_cover_paragraph_breaks():
    assert check("[5]", "[5]", drop_note_markers=["[5]"]).items[0].status == "exact"
    for source in ("가\n\n나", "가\r\n\r\n나", "가\n \n나"):
        r = verify_excerpt(
            ExcerptRequest(
                source_text=source,
                segments=[
                    {"start": 0, "end": 1, "quote": "가"},
                    {"start": len(source) - 1, "end": len(source), "quote": "나"},
                ],
            )
        )
        assert r.error is None and r.omissions[0].start == 1
        assert r.omissions[0].end == len(source) - 1
