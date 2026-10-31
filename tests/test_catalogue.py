import httpx
import pytest

from korean_lit_mcp.catalogue import NationalLibrary, parse_response
from korean_lit_mcp.contracts import SearchRequest
from korean_lit_mcp.sources import SourceError

# Synthetic XML uses fields documented by NL. Authenticated live shape is a Gate 0 check.
XML = b"""<root><total>1</total><item><control_no>test-id</control_no>
<title_info>Synthetic title</title_info><author_info>Tester</author_info>
<pub_year_info>1935</pub_year_info><doc_yn>Y</doc_yn></item></root>"""


async def test_cache_and_metadata_only() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["key"] == "fixture-key"
        return httpx.Response(200, content=XML)

    catalogue = NationalLibrary("fixture-key", transport=httpx.MockTransport(respond))
    request = SearchRequest(query="Synthetic")
    first = await catalogue.search(request)
    second = await catalogue.search(request)
    assert calls == 1
    assert first.retrieved_at == second.retrieved_at
    assert first.items[0]["available_text"] is False
    assert first.items[0]["copyright"] == "unknown"
    assert "fixture-key" not in repr(catalogue.cache.entries)


@pytest.mark.parametrize(
    "body",
    [
        b"bad xml",
        b"<error><error_code>010</error_code></error>",
        b"<root><total>5</total></root>",
        b'<!DOCTYPE x [<!ENTITY y "x">]><root/>',
    ],
)
def test_bad_upstream_never_becomes_empty_success(body: bytes) -> None:
    with pytest.raises(SourceError):
        parse_response(body)


def test_utf16_entities_are_rejected() -> None:
    body = '<!DOCTYPE x [<!ENTITY y "x">]><root><total>0</total></root>'.encode("utf-16")
    with pytest.raises(SourceError):
        parse_response(body)


def test_stdlib_xml_accepts_utf8_prolog() -> None:
    records, total = parse_response(b'<?xml version="1.0" encoding="UTF-8"?>' + XML)
    assert total == 1
    assert records[0]["control_no"] == "test-id"


async def test_errors_do_not_poison_cache() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429 if calls == 1 else 200, content=XML)

    catalogue = NationalLibrary("fixture-key", transport=httpx.MockTransport(respond))
    with pytest.raises(SourceError) as error:
        await catalogue.search(SearchRequest(query="q"))
    assert error.value.code == "upstream_limit"
    assert await catalogue.search(SearchRequest(query="q"))
    assert calls == 2


async def test_empty_results_expire_in_sixty_seconds() -> None:
    calls = 0
    now = [0.0]

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"<root><total>0</total></root>")

    catalogue = NationalLibrary("fixture-key", transport=httpx.MockTransport(respond))
    catalogue.cache.clock = lambda: now[0]
    request = SearchRequest(query="none")
    await catalogue.search(request)
    now[0] = 59
    await catalogue.search(request)
    assert calls == 1
    now[0] = 60
    await catalogue.search(request)
    assert calls == 2
