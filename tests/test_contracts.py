import pytest
from pydantic import ValidationError

from korean_lit_mcp.contracts import (
    Envelope,
    ErrorInfo,
    PassageRequest,
    SearchRequest,
    Source,
    VerifyRequest,
)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"quotes": ["인용"], "source_text": " "},
        {"quotes": [], "source_text": "원문"},
        {"quotes": ["인용"], "draft": "초안", "source_text": "원문"},
        {"quotes": ["인용"], "work_id": "book", "source_text": "원문"},
        {"quotes": ["인용"], "work_id": "book"},
        {"quotes": ["x"] * 21, "source_text": "원문"},
        {"quotes": ["x" * 2001], "source_text": "원문"},
        {"quotes": ["인용"], "source_text": "x" * 50001},
        {"quotes": ["인용"], "source_text": "원문", "save": True},
    ],
)
def test_invalid_verification_inputs(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        VerifyRequest.model_validate(payload)


def test_text_is_preserved() -> None:
    text = "  옛 表記\r\n\n그대로.  "
    request = VerifyRequest(quotes=[text], source_text=text)
    assert request.source_text == text
    assert request.quotes == [text]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "작품"},
        {"work_id": "x", "title": "작품"},
        {"work_id": "x", "start": 2, "end": 1},
        {"work_id": "x", "end": 50001},
    ],
)
def test_invalid_passage_inputs(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PassageRequest.model_validate(payload)


def test_search_range_and_limit() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="작품", year_from=2000, year_to=1900)
    with pytest.raises(ValidationError):
        SearchRequest(query="작품", limit=21)


def test_error_response_cannot_contain_successful_items() -> None:
    with pytest.raises(ValidationError):
        Envelope[int](
            items=[1], source=Source(name="test"), error=ErrorInfo(code="error", message="failure")
        )
