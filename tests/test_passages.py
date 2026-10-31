from pathlib import Path

from fastmcp import Client

from korean_lit_mcp.contracts import PassageRequest, SearchRequest
from korean_lit_mcp.passages import get_passage, search_works
from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import load_editions


def test_search_and_get_original_range() -> None:
    editions = load_editions(Path("data/works"))
    search = search_works(SearchRequest(query="봄봄", author="김유정"), editions)
    assert len(search.items) == 1
    assert search.items[0]["title"] == "봄·봄"
    assert search.copyright == "public_domain"
    assert get_passage(PassageRequest(title="봄봄", author="김유정"), editions).error is None
    passage = get_passage(PassageRequest(work_id="gongu-9000404", start=2, end=3), editions)
    assert passage.error is None
    paragraphs = passage.items[0]["paragraphs"]
    assert isinstance(paragraphs, list)
    original = editions[0].text
    assert (
        "".join(p["text"] for p in paragraphs)
        == original[paragraphs[0]["start"] : paragraphs[-1]["end"]]
    )


def test_missing_invalid_and_empty() -> None:
    editions = load_editions(Path("data/works"))
    assert get_passage(PassageRequest(work_id="missing"), editions).error.code == "not_found"
    assert (
        get_passage(PassageRequest(work_id="gongu-9000397", start=50000), editions).error.code
        == "invalid_range"
    )
    assert search_works(SearchRequest(query="없는 합성 작품"), editions).note
    assert search_works(SearchRequest(query="꽃김"), editions).items == []
    assert search_works(SearchRequest(query="·"), editions).items == []


def test_ambiguous_edition_not_selected() -> None:
    editions = load_editions(Path("data/works"))
    result = get_passage(PassageRequest(work_id="gongu-9000397"), editions + editions)
    assert result.error is not None
    assert result.error.code == "ambiguous_edition"


async def test_real_passage_tool() -> None:
    server = create_server(editions=load_editions(Path("data/works")))
    async with Client(server) as client:
        result = await client.call_tool(
            "get_passage", {"request": {"work_id": "gongu-9000397", "start": 2, "end": 2}}
        )
        assert result.structured_content["copyright"] == "public_domain"
        assert result.structured_content["items"][0]["address_basis"] == "source_lines"
