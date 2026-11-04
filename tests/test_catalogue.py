import logging

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


def test_unknown_error_content_is_not_reflected_to_teacher() -> None:
    with pytest.raises(SourceError) as error:
        parse_response(b"<error><error_code>private-key-marker</error_code></error>")
    assert "private-key-marker" not in str(error.value)
    assert error.value.code == "upstream_invalid"


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


async def test_upstream_error_metrics_exclude_credentials(caplog) -> None:
    caplog.set_level(logging.INFO, logger="korean_lit_mcp.catalogue")
    catalogue = NationalLibrary(
        "fixture-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=b"<error><error_code>011</error_code></error>"
            )
        ),
    )
    with pytest.raises(SourceError):
        await catalogue.search(SearchRequest(query="Synthetic"))
    assert "code=upstream_auth" in caplog.text
    assert "fixture-key" not in caplog.text


async def test_empty_control_number_and_duplicate_control_numbers_are_distinct():
    raw = b"""<root><total>2</total><item><id>synthetic-001</id><control_no/>
    <title_info>Synthetic online title</title_info><doc_yn>NL_VIEWER</doc_yn>
    <detail_link>/NL/contents/search.do#viewKey=synthetic-001&amp;viewType=C</detail_link>
    <org_link>https://viewer.nl.go.kr/example?cno=synthetic-001</org_link>
    <lic_yn>N</lic_yn><lic_text>Synthetic access note</lic_text></item>
    <item><id>synthetic-002</id><control_no>synthetic-control</control_no>
    <title_info>Synthetic second title</title_info><org_link>unavailable</org_link>
    <doc_yn>N</doc_yn><lic_yn>N</lic_yn></item></root>"""
    library = NationalLibrary(
        "fixture-key", transport=httpx.MockTransport(lambda r: httpx.Response(200, content=raw))
    )
    result = await library.search(SearchRequest(query="Synthetic"))
    first, second = result.items
    assert first["work_id"] == "nl-id-synthetic-001"
    assert first["record_id"] != second["record_id"]
    assert first["control_no"] is None and first["catalogue_id"] == "synthetic-001"
    assert (
        first["url"]
        == "https://www.nl.go.kr/NL/contents/search.do#viewKey=synthetic-001&viewType=C"
    )
    assert first["original_type"] == "NL_VIEWER" and first["access_code"] == "N"
    assert first["original_url"] == "https://viewer.nl.go.kr/example?cno=synthetic-001"
    assert first["available_text"] is False and first["copyright"] == "unknown"
    assert second["original_url"] is None
    # The same control number may describe multiple articles or online/offline records.
    raw = raw.replace(b"<control_no/>", b"<control_no>synthetic-control</control_no>")
    result = await NationalLibrary(
        "fixture-key", transport=httpx.MockTransport(lambda r: httpx.Response(200, content=raw))
    ).search(SearchRequest(query="Synthetic"))
    assert result.items[0]["work_id"] == result.items[1]["work_id"]
    assert result.items[0]["record_id"] != result.items[1]["record_id"]


@pytest.mark.parametrize("fields", [b"<control_no/>", b"<id> </id>", b"<id>x/y</id>"])
def test_missing_or_unsafe_identifiers_fail_explicitly(fields):
    with pytest.raises(SourceError):
        parse_response(
            b"<root><total>1</total><item><title_info>Synthetic</title_info>"
            + fields
            + b"</item></root>"
        )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1935", 1935),
        ("20130124", 2013),
        ("Era 9 (1920)", 1920),
        ("Era 4283[1950]", 1950),
        ("Era 429219", None),
        ("Unknown era", None),
    ],
)
def test_era_year_is_not_silently_a_gregorian_year(value, expected):
    from korean_lit_mcp.catalogue import publication_year

    assert publication_year(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "//untrusted.example/",
        "unavailable",
        "https://u:p@example.com/",
        "https://example.com/?key=synthetic",
        "https://example.com/?API_KEY=synthetic",
    ],
)
def test_unsafe_or_credential_links_are_not_returned(value):
    from korean_lit_mcp.catalogue import public_link

    assert public_link(value) is None
    assert public_link(value, detail=True) is None


async def test_category_cache_and_upstream_query_are_separate():
    categories = []

    def respond(request):
        categories.append(request.url.params.get("category"))
        return httpx.Response(200, content=XML)

    library = NationalLibrary("fixture-key", transport=httpx.MockTransport(respond))
    await library.search(SearchRequest(query="Synthetic"))
    await library.search(SearchRequest(query="Synthetic", nl_category="old_books"))
    await library.search(SearchRequest(query="Synthetic", nl_category="old_books"))
    await library.search(SearchRequest(query="Synthetic", mode="catalogue"))
    assert categories == ["도서", "고문헌", None]


async def test_echoed_secret_never_enters_cache_logs_or_result(caplog):
    raw = XML.replace(
        b"</item>", b"<org_link>https://example.com/?key=fixture-key</org_link></item>"
    )
    library = NationalLibrary(
        "fixture-key", transport=httpx.MockTransport(lambda r: httpx.Response(200, content=raw))
    )
    with pytest.raises(SourceError) as error:
        await library.search(SearchRequest(query="Synthetic"))
    assert error.value.code == "upstream_invalid"
    assert not library.cache.entries
    assert "fixture-key" not in str(error.value) and "fixture-key" not in caplog.text


async def test_more_records_than_requested_is_an_explicit_error():
    item = XML.split(b"<item>")[1].split(b"</item>")[0]
    raw = (
        b"<root><total>21</total>"
        + b"".join(
            b"<item>" + item.replace(b"test-id", f"test-{i}".encode()) + b"</item>"
            for i in range(21)
        )
        + b"</root>"
    )
    library = NationalLibrary(
        "fixture-key", transport=httpx.MockTransport(lambda r: httpx.Response(200, content=raw))
    )
    with pytest.raises(SourceError) as error:
        await library.search(SearchRequest(query="Synthetic"))
    assert error.value.code == "upstream_invalid" and not library.cache.entries
