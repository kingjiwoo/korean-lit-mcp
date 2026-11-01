import httpx
import pytest
from fastmcp import Client

from korean_lit_mcp.classical import ClassicalLibrary, ClassicalSearchRequest, parse_response
from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import SourceError


@pytest.fixture(autouse=True)
def endpoint(monkeypatch):
    monkeypatch.setenv("ITKC_API_URL", "https://itkc.example/search")


XML = b"""<response><header><field name="totalCount">1</field></header><result><doc>
<field name="\xec\x9e\x90\xeb\xa3\x8cID">ITKC_GO_test</field>
<field name="\xea\xb8\xb0\xec\x82\xac\xeb\xaa\x85">Test</field>
<field name="\xea\xb2\x80\xec\x83\x89\xed\x95\x84\xeb\x93\x9c">A &lt;em&gt;B&lt;/em&gt;</field>
</doc></result></response>"""


async def test_search_and_cache():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.params["secId"] == "GO_BD"
        assert request.url.params["keyword"] == "test"
        return httpx.Response(200, content=XML)

    library = ClassicalLibrary(transport=httpx.MockTransport(handler))
    query = ClassicalSearchRequest(query="test")
    result = await library.search(query)
    assert result.items[0]["is_excerpt"] is True
    assert result.items[0]["available_text"] is False
    assert result.items[0]["snippet"] == "A <em>B</em>"
    assert result.copyright == "unknown"
    assert (await library.search(query)).retrieved_at == result.retrieved_at
    assert len(calls) == 1


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"<html/>",
        b"<!DOCTYPE x><response/>",
        b'<response><header><field name="totalCount">1</field></header></response>',
    ],
)
def test_invalid_xml(raw):
    with pytest.raises(SourceError):
        parse_response(raw)


@pytest.mark.parametrize("status,code", [(429, "upstream_limit"), (500, "upstream_unavailable")])
async def test_failure(status, code):
    library = ClassicalLibrary(transport=httpx.MockTransport(lambda r: httpx.Response(status)))
    with pytest.raises(SourceError) as error:
        await library.search(ClassicalSearchRequest(query="test"))
    assert error.value.code == code


async def test_mcp_error_is_explicit(monkeypatch):
    async def fail(self, request):
        raise SourceError("upstream_invalid", "invalid")

    monkeypatch.setattr(ClassicalLibrary, "search", fail)
    async with Client(create_server()) as client:
        result = await client.call_tool("search_classical_text", {"request": {"query": "test"}})
        assert result.structured_content["error"]["code"] == "upstream_invalid"


async def test_unconfigured(monkeypatch):
    monkeypatch.delenv("ITKC_API_URL")
    with pytest.raises(SourceError) as error:
        await ClassicalLibrary().search(ClassicalSearchRequest(query="test"))
    assert error.value.code == "upstream_not_configured"


@pytest.mark.parametrize(
    "url", ["http://example.com", "https://u:p@example.com", "https://example.com?q=x"]
)
def test_invalid_endpoint(monkeypatch, url):
    monkeypatch.setenv("ITKC_API_URL", url)
    with pytest.raises(ValueError):
        ClassicalLibrary()


async def test_title_search_and_empty_result():
    def handler(request):
        assert request.url.params["secId"] == "MO_GS"
        return httpx.Response(
            200,
            content=(
                b'<response><header><field name="totalCount">0</field></header><result/></response>'
            ),
        )

    library = ClassicalLibrary(transport=httpx.MockTransport(handler))
    result = await library.search(
        ClassicalSearchRequest(query="test", collection="anthology", target="title")
    )
    assert result.items == []
    assert result.error is None


async def test_response_size_limit():
    library = ClassicalLibrary(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))
        )
    )
    with pytest.raises(SourceError) as error:
        await library.search(ClassicalSearchRequest(query="test"))
    assert error.value.code == "upstream_invalid"


@pytest.mark.parametrize(
    "collection,section", [("classic", "GO_BD"), ("anthology", "MO_BD"), ("corpus", "KP_BD")]
)
async def test_collection_mapping(collection, section):
    def handler(request):
        assert request.url.params["secId"] == section
        return httpx.Response(200, content=XML)

    await ClassicalLibrary(transport=httpx.MockTransport(handler)).search(
        ClassicalSearchRequest(query="test", collection=collection)
    )


async def test_busy(monkeypatch):
    library = ClassicalLibrary()

    async def busy(*args, **kwargs):
        raise TimeoutError

    monkeypatch.setattr(library.cache, "get", busy)
    with pytest.raises(SourceError) as error:
        await library.search(ClassicalSearchRequest(query="test"))
    assert error.value.code == "upstream_busy"


async def test_too_many_results():
    raw = XML.replace(b">1</field>", b">2</field>").replace(
        b"</result>", XML.split(b"<result>")[1].split(b"</result>")[0] + b"</result>"
    )
    library = ClassicalLibrary(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=raw))
    )
    with pytest.raises(SourceError) as error:
        await library.search(ClassicalSearchRequest(query="test", limit=1))
    assert error.value.code == "upstream_invalid"


async def test_mcp_unconfigured(monkeypatch):
    monkeypatch.delenv("ITKC_API_URL")
    async with Client(create_server()) as client:
        result = await client.call_tool("search_classical_text", {"request": {"query": "test"}})
        assert result.structured_content["error"]["code"] == "upstream_not_configured"
