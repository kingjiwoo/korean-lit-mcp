import logging
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from korean_lit_mcp.grammar import load_grammar
from korean_lit_mcp.runtime import create_http_app
from korean_lit_mcp.sources import load_editions


def app():
    return create_http_app(
        editions=load_editions(Path("data/works")),
        grammar_entries=load_grammar(Path("data/grammar")),
        allowed_hosts=["testserver"],
    )


def test_public_tools_do_not_require_login() -> None:
    with TestClient(app()) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/health").status_code == 405
        headers = {"Accept": "application/json, text/event-stream"}
        response = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert response.status_code == 200
        assert {t["name"] for t in response.json()["result"]["tools"]} == {
            "search_works",
            "search_classical_text",
            "get_passage",
            "verify_quote",
            "lookup_grammar",
        }
        assert response.headers["cache-control"] == "no-store"
        assert "www-authenticate" not in response.headers


def test_public_rate_and_body_guards() -> None:
    guarded = app()
    guarded.clock = lambda: 0.0
    with TestClient(guarded) as client:
        response = client.post("/mcp", content=b"x" * (1024 * 1024 + 1))
        assert response.status_code == 413
        assert response.headers["cache-control"] == "no-store"
        for _ in range(29):
            client.post("/mcp", content=b"{}")
        limited = client.post("/mcp", content=b"{}")
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == "60"
        guarded.clock = lambda: 61.0
        assert client.post("/mcp", content=b"{}").status_code != 429


@pytest.mark.parametrize("hosts", [[], ["*"]])
def test_public_server_requires_explicit_hosts(hosts: list[str]) -> None:
    with pytest.raises(ValueError, match="MCP_ALLOWED_HOSTS"):
        create_http_app(editions=(), allowed_hosts=hosts)


def test_untrusted_origin_and_host_are_rejected() -> None:
    with TestClient(app()) as client:
        headers = {"Accept": "application/json, text/event-stream"}
        assert (
            client.post(
                "/mcp", headers={**headers, "Origin": "https://untrusted.example"}, json={}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/mcp", headers={**headers, "Host": "untrusted.example"}, json={}
            ).status_code
            == 421
        )


def test_rejected_input_and_headers_do_not_appear_in_logs(caplog) -> None:
    caplog.set_level(logging.INFO, logger="korean_lit_mcp.metrics")
    secret = "private_source_marker" + "x" * 50000
    with TestClient(app()) as client:
        client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer private_header_marker",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "verify_quote",
                    "arguments": {
                        "request": {
                            "source_text": secret,
                            "quotes": ["인용"],
                        }
                    },
                },
            },
        )
    assert "private_source_marker" not in caplog.text
    assert "private_header_marker" not in caplog.text
    assert "name=verify_quote" in caplog.text


def test_grammar_metrics_do_not_record_query_text(caplog) -> None:
    caplog.set_level(logging.INFO, logger="korean_lit_mcp.metrics")
    marker = "private_grammar_query_marker"
    with TestClient(app()) as client:
        response = client.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "lookup_grammar",
                    "arguments": {"request": {"term": marker, "period": "modern"}},
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["result"]["structuredContent"]["items"] == []
    assert marker not in caplog.text
    assert "name=lookup_grammar" in caplog.text
