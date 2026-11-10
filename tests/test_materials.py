import json
from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import ValidationError
from starlette.testclient import TestClient

from korean_lit_mcp.materials import MaterialRequest, review_material
from korean_lit_mcp.runtime import create_http_app
from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import load_editions


def block(text="봄이 온다.", **changes):
    return {
        "block_id": "p1",
        "kind": "passage",
        "text": text,
        "citations": [{"start": 0, "end": len(text), "source_start": 0, "source_end": 9}],
        **changes,
    }


def test_report_uses_real_block_text_and_keeps_unverified_ranges():
    r = review_material(
        MaterialRequest(
            source_text="봄[1]이 온다.",
            rules={"drop_note_markers": ["[1]"]},
            blocks=[
                block(),
                block("해설은 미검증", block_id="e1", kind="explanation", citations=[]),
            ],
        )
    )
    assert r.checked_count == r.review_required_count == 1
    assert not r.all_submitted_raw_exact
    assert r.items[0].citations[0].comparison.status == "edited_match"
    assert r.items[0].citations[0].comparison.quote == "봄이 온다."
    assert r.items[1].unverified_ranges[0].end == len("해설은 미검증")
    assert r.unverified_character_count == len("해설은 미검증")
    r = review_material(
        MaterialRequest(source_text="봄[1]이 온다.", blocks=[block("안 봄이 온다.")])
    )
    assert r.items[0].citations[0].comparison.status == "mismatch"


def test_exact_citations_do_not_certify_unsubmitted_text_or_empty_reports():
    text = "설명 봄이 온다. 나머지"
    request = MaterialRequest(
        source_text="봄이 온다.",
        blocks=[
            block(text, citations=[{"start": 3, "end": 9, "source_start": 0, "source_end": 6}])
        ],
    )
    r = review_material(request)
    assert r.all_submitted_raw_exact and r.unverified_character_count == len(text) - 6
    assert [(g.start, g.end) for g in r.items[0].unverified_ranges] == [(0, 3), (9, len(text))]
    empty = review_material(
        MaterialRequest(source_text="합성", blocks=[block("설명", citations=[])])
    )
    assert empty.checked_count == 0 and not empty.all_submitted_raw_exact
    assert empty.unverified_character_count == 2


@pytest.mark.parametrize(
    "blocks",
    [
        [block(), block()],
        [block(citations=[{"start": 0, "end": 10, "source_start": 0, "source_end": 9}])],
        [block("가  나", citations=[{"start": 1, "end": 3, "source_start": 0, "source_end": 2}])],
        [
            block(
                citations=[
                    {"start": 0, "end": 4, "source_start": 0, "source_end": 3},
                    {"start": 3, "end": 5, "source_start": 4, "source_end": 6},
                ]
            )
        ],
        [block(citations=[{"start": 0, "end": 2, "source_start": 3, "source_end": 2}])],
        [block("가" * 30000, citations=[]), block("나", block_id="extra", citations=[])],
    ],
)
def test_report_rejects_invalid_structures(blocks):
    with pytest.raises(ValidationError):
        MaterialRequest(source_text="봄[1]이 온다.", blocks=blocks)


def test_source_range_error_never_becomes_partial_report():
    r = review_material(
        MaterialRequest(
            source_text="봄",
            blocks=[
                block("봄", citations=[{"start": 0, "end": 1, "source_start": 0, "source_end": 1}]),
                block(
                    "봄",
                    block_id="bad",
                    citations=[{"start": 0, "end": 1, "source_start": 2, "source_end": 3}],
                ),
            ],
        )
    )
    assert r.error.code == "invalid_range" and not r.items and r.checked_count == 0
    assert not r.all_submitted_raw_exact


def test_real_http_search_to_material_report_and_stale_edition():
    es = load_editions(Path("data/works"))
    e = next(e for e in es if e.manifest.title == "규원가")
    ids = {"work_id": e.manifest.work_id, "edition_id": e.manifest.edition_id}
    with TestClient(
        create_http_app(editions=es, allowed_hosts=["localhost"]), base_url="http://localhost"
    ) as client:

        def call(tool, request):
            r = client.post(
                "/mcp",
                headers={"Accept": "application/json, text/event-stream"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": {"request": request}},
                },
            )
            assert r.status_code == 200
            return r.json()["result"]["structuredContent"]

        found = call("find_passage", {**ids, "query": "서른[5] 말ᄉᆞᆷ"})
        hit = found["items"][0]
        quote = hit["text"].replace("[5]", "")
        citation = {
            "start": 0,
            "end": len(quote),
            "source_start": hit["location"]["start"],
            "source_end": hit["location"]["end"],
        }
        args = {
            **ids,
            "source_hash": found["source_hash"],
            "blocks": [block(quote, citations=[citation])],
            "rules": {"drop_note_markers": ["[5]"]},
        }
        result = call("review_material", args)
        assert result["items"][0]["citations"][0]["comparison"]["status"] == "edited_match"
        excerpt = call(
            "verify_excerpt",
            {
                **ids,
                "source_hash": found["source_hash"],
                "segments": [
                    {
                        "start": citation["source_start"],
                        "end": citation["source_end"],
                        "quote": quote,
                    }
                ],
                "rules": args["rules"],
            },
        )
        assert excerpt["items"][0] == result["items"][0]["citations"][0]["comparison"]
        assert (
            call("review_material", {**args, "source_hash": "0" * 64})["error"]["code"]
            == "source_changed"
        )


async def test_private_material_never_calls_network_or_logs_content(monkeypatch, caplog):
    async def no_network(*a, **kw):
        raise AssertionError("Material review must stay local")

    monkeypatch.setattr(httpx.AsyncClient, "send", no_network)
    private = "비공개 합성 교사 본문"
    async with Client(create_server()) as c:
        r = (
            await c.call_tool(
                "review_material",
                {"request": {"source_text": private, "blocks": [block(private, citations=[])]}},
            )
        ).structured_content
        assert r["checked_count"] == 0 and r["unverified_character_count"] == len(private)
        assert private not in caplog.text
        with pytest.raises(ToolError):
            await c.call_tool(
                "review_material",
                {
                    "request": {
                        "source_text": private,
                        "blocks": [
                            block(
                                private,
                                citations=[
                                    {"start": 0, "end": 500, "source_start": 0, "source_end": 1}
                                ],
                            )
                        ],
                    }
                },
            )
        assert private not in caplog.text


def test_report_payload_bound_for_maximum_selected_text():
    source = "".join(chr(0x20000 + i) for i in range(10000))
    blocks = [
        block(
            source[s : s + 2000],
            block_id=f"p{s}",
            citations=[{"start": 0, "end": 2000, "source_start": s, "source_end": s + 2000}],
        )
        for s in range(0, 10000, 2000)
    ]
    result = review_material(MaterialRequest(source_text=source, blocks=blocks))
    assert result.checked_count == 5 and result.all_submitted_raw_exact
    assert len(json.dumps(result.model_dump(mode="json"), ensure_ascii=False).encode()) < 512 * 1024
    with TestClient(
        create_http_app(editions=(), allowed_hosts=["localhost"]), base_url="http://localhost"
    ) as client:
        response = client.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "review_material",
                    "arguments": {"request": {"source_text": source, "blocks": blocks}},
                },
            },
        )
        assert response.status_code == 200 and len(response.content) < 1024 * 1024
        assert response.json()["result"]["structuredContent"]["checked_count"] == 5


def test_aggregate_citation_and_selected_text_limits():
    citations = [{"start": i, "end": i + 1, "source_start": 0, "source_end": 1} for i in range(11)]
    with pytest.raises(ValidationError, match="20 citations"):
        MaterialRequest(
            source_text="가",
            blocks=[block("가" * 11, block_id=f"p{i}", citations=citations) for i in range(2)],
        )
    with pytest.raises(ValidationError, match="10000"):
        MaterialRequest(
            source_text="가" * 12000,
            blocks=[
                block(
                    "가가가",
                    citations=[
                        {
                            "start": i,
                            "end": i + 1,
                            "source_start": i * 4000,
                            "source_end": (i + 1) * 4000,
                        }
                        for i in range(3)
                    ],
                )
            ],
        )
