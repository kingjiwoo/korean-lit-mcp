import runpy

import pytest
from starlette.testclient import TestClient

from korean_lit_mcp.runtime import create_app_from_env

REQUEST = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in (
        "MCP_ALLOWED_HOSTS",
        "MCP_ALLOWED_ORIGINS",
        "NL_API_KEY",
        "WORKS_DIR",
        "VERCEL_URL",
        "VERCEL_BRANCH_URL",
        "VERCEL_PROJECT_PRODUCTION_URL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    "variable", ["VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"]
)
def test_platform_host_is_allowed_without_opening_other_hosts(monkeypatch, variable) -> None:
    monkeypatch.setenv(variable, "deployment.example")
    with TestClient(create_app_from_env(), base_url="https://deployment.example") as client:
        assert client.post("/mcp", headers=HEADERS, json=REQUEST).status_code == 200
        assert (
            client.post(
                "/mcp", headers={**HEADERS, "Host": "untrusted.example"}, json=REQUEST
            ).status_code
            == 421
        )


def test_explicit_hosts_override_platform_hosts(monkeypatch) -> None:
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", " configured.example , secondary.example ")
    monkeypatch.setenv("VERCEL_URL", "deployment.example")
    with TestClient(create_app_from_env(), base_url="https://configured.example") as client:
        assert client.post("/mcp", headers=HEADERS, json=REQUEST).status_code == 200
        assert (
            client.post(
                "/mcp", headers={**HEADERS, "Host": "secondary.example"}, json=REQUEST
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/mcp", headers={**HEADERS, "Host": "deployment.example"}, json=REQUEST
            ).status_code
            == 421
        )


def test_empty_explicit_hosts_do_not_fall_back_to_platform_hosts(monkeypatch) -> None:
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", " , ")
    monkeypatch.setenv("VERCEL_URL", "deployment.example")
    with pytest.raises(ValueError, match="MCP_ALLOWED_HOSTS"):
        create_app_from_env()


def test_local_defaults_allow_localhost() -> None:
    with TestClient(create_app_from_env(), base_url="http://localhost") as client:
        assert client.post("/mcp", headers=HEADERS, json=REQUEST).status_code == 200


def test_vercel_entrypoint_loads_reviewed_texts(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL_URL", "deployment.example")
    entrypoint = runpy.run_path("app.py")["app"]
    with TestClient(entrypoint, base_url="https://deployment.example") as client:
        response = client.post(
            "/mcp",
            headers=HEADERS,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get_passage",
                    "arguments": {"request": {"work_id": "gongu-9000397", "start": 2, "end": 2}},
                },
            },
        )
        assert response.status_code == 200
        passage = response.json()["result"]["structuredContent"]["items"][0]
        assert passage["work_id"] == "gongu-9000397"
        assert passage["paragraphs"][0]["text"]
        assert passage["source_hash"]
