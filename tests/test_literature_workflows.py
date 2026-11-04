"""Teacher retrieval/quotation flow through the actual HTTP MCP boundary."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from korean_lit_mcp.runtime import create_http_app
from korean_lit_mcp.sources import load_editions


@pytest.mark.parametrize(
    "title", ["사미인곡", "청산별곡", "관동별곡", "규원가", "홍길동전", "구운몽"]
)
def test_teacher_http_workflow_and_search_budget(title):
    app = create_http_app(editions=load_editions(Path("data/works")), allowed_hosts=["localhost"])
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
            return response, response.json()["result"]["structuredContent"]

        response, found = call("search_works", {"query": title})
        assert len(response.content) <= 16 * 1024
        assert found["search_context"]["request"]["query"] == title
        available = [i for i in found["items"] if i["available_text"]]
        if title == "구운몽":
            assert not available
            assert found["search_context"]["outcome"] == "work_identified"
            assert found["items"][0]["next_searches"]
            return
        assert available
        for selected in available:
            ids = {k: selected[k] for k in ("work_id", "edition_id")}
            _, passage = call("get_passage", {**ids, "start": 3, "end": 4})
            assert passage["error"] is None
            item = passage["items"][0]
            quote = next(p["text"] for p in item["paragraphs"] if p["text"].strip())[:150]
            request = {**ids, "source_hash": item["source_hash"], "quotes": [quote]}
            _, exact = call("verify_quote", request)
            assert exact["items"][0]["status"] == "exact"
            assert exact["reference_basis"] == "reviewed_edition"
            _, changed = call("verify_quote", {**request, "quotes": [quote + "[합성 변경]"]})
            assert changed["items"][0]["status"] != "exact"
            assert changed["items"][0]["requires_review"]
            _, repaired = call("verify_quote", request)
            assert repaired["items"][0]["status"] == "exact"
            _, stale = call("verify_quote", {**request, "source_hash": "0" * 64})
            assert stale["error"]["code"] == "source_changed"
            if title == "홍길동전":
                other = next(i for i in available if i["edition_id"] != ids["edition_id"])
                _, wrong = call("verify_quote", {**request, "edition_id": other["edition_id"]})
                assert wrong["error"]["code"] == "source_changed"
