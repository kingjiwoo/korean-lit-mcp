import unicodedata
from pathlib import Path

import pytest
from fastmcp import Client

from korean_lit_mcp.contracts import VerifyRequest
from korean_lit_mcp.server import create_server
from korean_lit_mcp.sources import load_editions
from korean_lit_mcp.verification import verify_quote


def check(source: str, quote: str):
    return verify_quote(VerifyRequest(source_text=source, quotes=[quote])).items[0]


def test_exact_offsets_and_paragraphs() -> None:
    source = "첫 문단.\r\n\r\n다음 원문입니다."
    result = check(source, "다음 원문입니다.")
    assert result.status == "exact"
    location = result.locations[0]
    assert source[location.start : location.end] == result.quote
    assert location.paragraph_start == 2


@pytest.mark.parametrize(
    "source,quote",
    [
        ("산에 간다.", "산에  간다."),
        ("“인용”이다.", '"인용"이다.'),
        (unicodedata.normalize("NFD", "한글 인용이다."), "한글 인용이다."),
        ("한글 인용이다.", unicodedata.normalize("NFD", "한글 인용이다.")),
    ],
)
def test_orthography_has_raw_candidate(source: str, quote: str) -> None:
    result = check(source, quote)
    assert result.status == "orthography"
    assert result.requires_review
    assert result.suggestion in source
    assert check(source, result.suggestion).status == "exact"


@pytest.mark.parametrize(
    "quote", ["나는 산에 안 간다.", "나는 바다에 간다.", "나는 산에 3번 간다."]
)
def test_lexical_changes_never_pass(quote: str) -> None:
    result = check("나는 산에 간다.", quote)
    assert result.status in {"mismatch", "not_found"}
    assert result.requires_review


def test_missing_and_repeated_quotes() -> None:
    assert check("원문에 있는 내용.", "우주선은 날아갔다.").status == "not_found"
    result = check("같은 인용. 또 같은 인용.", "같은 인용.")
    assert result.status == "exact"
    assert result.requires_review
    assert len(result.locations) == 2


def test_overlapping_occurrences_are_ambiguous() -> None:
    result = check("하하하", "하하")
    assert len(result.locations) == 2
    assert result.requires_review


def test_partial_hangul_syllable_is_not_orthography() -> None:
    assert check("각", "가").status == "not_found"


def test_hash_change_and_edition() -> None:
    editions = load_editions(Path("data/works"))
    manifest = editions[0].manifest
    result = verify_quote(
        VerifyRequest(
            quotes=["인용"],
            work_id=manifest.work_id,
            edition_id=manifest.edition_id,
            source_hash="0" * 64,
        ),
        editions,
    )
    assert result.error is not None and result.error.code == "source_changed"
    assert result.source == manifest.source


async def test_verify_tool_and_no_source_logs(caplog) -> None:
    secret = "교사 제공 비공개 합성 본문입니다."
    async with Client(create_server()) as client:
        result = await client.call_tool(
            "verify_quote", {"request": {"source_text": secret, "quotes": [secret]}}
        )
        assert result.structured_content["items"][0]["status"] == "exact"
    assert secret not in caplog.text
