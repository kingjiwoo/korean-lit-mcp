import logging
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from korean_lit_mcp.runtime import create_http_app
from korean_lit_mcp.sources import load_editions

TOKEN = "fixture-token-" + "x" * 32


def app(token: str = TOKEN):
    return create_http_app(
        token=token, editions=load_editions(Path("data/works")), allowed_hosts=["testserver"]
    )


def test_token_required_health_available_and_headers() -> None:
    with TestClient(app()) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/mcp").status_code == 401
        assert client.post("/mcp", content=b"x" * (1024 * 1024 + 1)).status_code == 401
        headers = {
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/json, text/event-stream",
        }
        response = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert response.status_code == 200
        assert {t["name"] for t in response.json()["result"]["tools"]} == {
            "search_works",
            "get_passage",
            "verify_quote",
        }
        assert response.headers["cache-control"] == "no-store"


def test_rate_body_and_duplicate_header_guards() -> None:
    guarded = app()
    guarded.clock = lambda: 0.0
    with TestClient(guarded) as client:
        headers = {"Authorization": "Bearer " + TOKEN}
        assert (
            client.post("/mcp", headers=headers, content=b"x" * (1024 * 1024 + 1)).status_code
            == 413
        )
        assert (
            client.post("/mcp", headers=[("Authorization", "Bearer " + TOKEN)] * 2).status_code
            == 400
        )
        for _ in range(29):
            client.post("/mcp", headers=headers, content=b"{}")
        assert client.post("/mcp", headers=headers, content=b"{}").status_code == 429
        guarded.clock = lambda: 61.0
        assert client.post("/mcp", headers=headers, content=b"{}").status_code != 429


def test_bad_configuration_fails_closed() -> None:
    with pytest.raises(ValueError, match="MCP_AUTH_TOKEN"):
        app("short")


def test_untrusted_origin_and_host_are_rejected() -> None:
    with TestClient(app()) as client:
        headers = {
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/json, text/event-stream",
        }
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


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_bearer_scheme_case_cannot_bypass_body_guard(scheme: str) -> None:
    with TestClient(app()) as client:
        response = client.post(
            "/mcp",
            headers={"Authorization": scheme + " " + TOKEN},
            content=b"x" * (1024 * 1024 + 1),
        )
        assert response.status_code == 413


def test_rejected_input_and_token_do_not_appear_in_logs(caplog) -> None:
    caplog.set_level(logging.INFO, logger="korean_lit_mcp.metrics")
    secret = "private_source_marker" + "x" * 50000
    with TestClient(app()) as client:
        client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer " + TOKEN,
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
    assert TOKEN not in caplog.text
    assert "name=verify_quote" in caplog.text
