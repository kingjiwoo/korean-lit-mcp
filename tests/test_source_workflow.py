"""Keyless workflows use reviewed editions or wholly synthetic teacher text."""

from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from starlette.testclient import TestClient

from korean_lit_mcp.catalogue import NationalLibrary
from korean_lit_mcp.classical import ClassicalLibrary
from korean_lit_mcp.contracts import Envelope, SearchRequest, Source
from korean_lit_mcp.passages import search_works
from korean_lit_mcp.runtime import create_http_app
from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import SourceError, load_editions


@pytest.mark.parametrize("has_editions", [True, False])
async def test_missing_work_is_not_an_empty_catalogue(has_editions):
    editions = load_editions(Path("data/works")) if has_editions else ()
    async with Client(create_server(editions=editions)) as client:
        result = await client.call_tool(
            "search_works", {"request": {"query": "청산별곡", "author": "합성 작가"}}
        )
    data = result.structured_content
    context = data["search_context"]
    # A caller can compare this actual query with their requested work (e.g. 규원가).
    assert context["request"]["query"] == "청산별곡"
    assert context["request"]["author"] == "합성 작가"
    assert context["scope"] == "reviewed_catalogue"
    assert (
        context["reviewed_work_count"]
        == context["reviewed_edition_count"]
        == (2 if has_editions else 0)
    )
    assert context["outcome"] == ("no_matches" if has_editions else "empty_catalogue")
    assert data["items"] == [] and data["error"] is None
    assert "추정" in data["note"] and "source_text" in data["note"]


@pytest.mark.parametrize("query,partial", [("김유정", True), ("합성 미수록 작품", False)])
async def test_nl_failure_keeps_query_and_local_inventory(monkeypatch, query, partial):
    async def fail(self, request):
        raise SourceError("upstream_unavailable", "합성 기관 장애")

    monkeypatch.setattr(NationalLibrary, "search", fail)
    async with Client(
        create_server(editions=load_editions(Path("data/works")), nl_api_key="fixture-key")
    ) as client:
        result = await client.call_tool("search_works", {"request": {"query": query}})
    data = result.structured_content
    context = data["search_context"]
    assert context["request"]["query"] == query
    assert context["scope"] == "reviewed_catalogue_and_nl"
    assert context["reviewed_work_count"] == 2
    assert context["upstream_error"]["code"] == "upstream_unavailable"
    assert context["outcome"] == ("partial_results" if partial else "upstream_error")
    assert bool(data["items"]) == partial
    assert (data["error"] is None) == partial


async def test_nl_metadata_success_is_not_a_passage(monkeypatch):
    async def metadata(self, request):
        return Envelope(
            source=Source(name="합성 기관"),
            items=[{"title": "합성 서지", "available_text": False}],
        )

    monkeypatch.setattr(NationalLibrary, "search", metadata)
    async with Client(create_server(nl_api_key="fixture-key")) as client:
        result = await client.call_tool("search_works", {"request": {"query": "합성 서지"}})
    data = result.structured_content
    assert data["search_context"]["outcome"] == "matches"
    assert data["search_context"]["reviewed_work_count"] == 0
    assert data["items"][0]["available_text"] is False


@pytest.mark.parametrize("mode", ["related", "empty", "failure"])
async def test_itkc_context_on_every_outcome(monkeypatch, mode):
    monkeypatch.setenv("ITKC_API_URL", "https://itkc.example/search")
    raw = (
        '<response><header><field name="totalCount">'
        + ("1" if mode == "related" else "0")
        + "</field></header><result>"
        + (
            '<doc><field name="자료ID">ITKC_GO_synthetic</field>'
            '<field name="기사명">합성 언급 기사</field>'
            '<field name="검색필드">합성 발췌</field></doc>'
            if mode == "related"
            else ""
        )
        + "</result></response>"
    ).encode()
    library = ClassicalLibrary(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(503 if mode == "failure" else 200, content=raw)
        )
    )
    original_search = library.search

    async def search(self, request):
        return await original_search(request)

    monkeypatch.setattr(ClassicalLibrary, "search", search)
    async with Client(create_server()) as client:
        result = await client.call_tool(
            "search_classical_text",
            {"request": {"query": "규원가", "collection": "anthology", "target": "title"}},
        )
    data = result.structured_content
    context = data["search_context"]
    assert context["request"] == {
        "query": "규원가",
        "collection": "anthology",
        "target": "title",
        "limit": 10,
    }
    assert context["scope"] == "itkc"
    assert context["reviewed_work_count"] is None
    assert (
        context["outcome"]
        == {"related": "related_records", "empty": "no_matches", "failure": "upstream_error"}[mode]
    )
    if mode == "related":
        assert data["items"][0]["available_text"] is False
    elif mode == "failure":
        assert data["error"]["code"] == "upstream_unavailable"


def test_http_search_and_teacher_text_correction_flow(caplog):
    app = create_http_app(editions=load_editions(Path("data/works")), allowed_hosts=["localhost"])
    source = "합성 옛표기 ᄒᆞ니 그대로 둔다.\n합성 둘째 행이다."
    changed = "합성 옛표기 하니 그대로 둔다."
    draft = f"<passage>{changed}</passage>\n표시 없는 합성 인용이다. 정답은 ④."
    with TestClient(app, base_url="http://localhost") as client:

        def call(name, request):
            response = client.post(
                "/mcp",
                headers={"Accept": "application/json, text/event-stream"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": {"request": request}},
                },
            )
            assert response.status_code == 200
            return response.json()["result"]["structuredContent"]

        missing = call("get_passage", {"work_id": "synthetic-unavailable"})
        assert missing["error"]["code"] == "not_found" and missing["items"] == []
        assert "원문을 반환하지 않았습니다" in missing["note"]
        result = call("verify_quote", {"source_text": source, "draft": draft})
        assert result["reference_basis"] == "supplied_text"
        assert not result["all_submitted_exact"]
        assert result["items"][0]["requires_review"]
        assert result["items"][0]["status"] in {"mismatch", "not_found", "orthography"}
        assert result["coverage"] == "supported_draft_regions" and result["checked_count"] == 1
        assert result["unverified_regions"]
        corrected = call(
            "verify_quote",
            {
                "source_text": source,
                "draft": f"<passage>{source.splitlines()[0]}</passage>\n정답은 ④.",
            },
        )
        assert corrected["all_submitted_exact"] and corrected["checked_count"] == 1
        assert "정본" in corrected["note"] and "문항 정답" in corrected["note"]
        assert corrected["unverified_regions"]  # The answer and unmarked prose remain unchecked.
        unsupported = call("verify_quote", {"source_text": source, "draft": "표시 없는 초안"})
        assert unsupported["error"]["code"] == "unverified_draft"
        assert not unsupported["all_submitted_exact"]
        # Passing a reconstructed source and the same quote proves only self-consistency.
        self_match = call("verify_quote", {"source_text": changed, "quotes": [changed]})
        assert self_match["all_submitted_exact"]
        assert self_match["reference_basis"] == "supplied_text" and "정본" in self_match["note"]
    assert source not in caplog.text and changed not in caplog.text and draft not in caplog.text


def test_search_filters_are_echoed():
    request = SearchRequest(query="동백꽃", author="김유정", year_from=1900, year_to=1950, limit=1)
    context = search_works(request, load_editions(Path("data/works"))).search_context
    assert context.request == request.model_dump(mode="json")
