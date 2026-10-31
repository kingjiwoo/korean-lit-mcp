from korean_lit_mcp.contracts import VerifyRequest
from korean_lit_mcp.drafts import extract_quotes
from korean_lit_mcp.verification import verify_quote


def test_supported_markers_and_offsets() -> None:
    draft = '문제: “첫 인용” 그리고 "둘째 인용". <passage>지문\n두 행</passage> ‘대사’'
    quotes, notes = extract_quotes(draft)
    assert [q.text for q in quotes] == ["첫 인용", "둘째 인용", "지문\n두 행", "대사"]
    assert all(draft[q.start : q.end] == q.text for q in quotes)
    assert any("미검증" in note for note in notes)


def test_missing_unclosed_and_nested_not_certified() -> None:
    for draft in ["인용 표시 없음", "“닫히지 않은 인용", '“바깥 "안쪽" 인용”']:
        quotes, notes = extract_quotes(draft)
        assert not quotes
        assert notes


def test_draft_verification_is_explicitly_partial() -> None:
    draft = "문제 “첫 인용” 정답 <quote>둘째 인용</quote> 다른 미표시 인용"
    result = verify_quote(VerifyRequest(draft=draft, source_text="첫 인용. 둘째 인용."))
    assert result.error is None
    assert result.coverage == "supported_draft_regions"
    assert result.checked_count == 2
    assert result.all_submitted_exact
    assert result.unverified_regions
    for quote in result.items:
        assert draft[quote.draft_start : quote.draft_end] == quote.quote


def test_zero_and_excessive_quotes_are_not_success() -> None:
    for draft in ["닫히지 않은 “인용", "빈칸 ____", '"인용" ' * 21]:
        result = verify_quote(VerifyRequest(draft=draft, source_text="인용"))
        assert result.error is not None
        assert not result.all_submitted_exact
