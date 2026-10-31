"""Deterministic quotation checks; supplied text exists only within the request."""

import unicodedata
from bisect import bisect_left, bisect_right
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from korean_lit_mcp.contracts import Envelope, ErrorInfo, Source, VerifyRequest
from korean_lit_mcp.sources import Edition, Paragraph, SourceError, select_edition, split_paragraphs

QUOTE_MARKS = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


class Location(BaseModel):
    start: int
    end: int
    paragraph_start: int
    paragraph_end: int


class QuoteResult(BaseModel):
    quote: str
    status: Literal["exact", "orthography", "mismatch", "not_found"]
    locations: list[Location] = Field(default_factory=list)
    requires_review: bool = False
    suggestion: str | None = None
    differences: list[dict[str, object]] = Field(default_factory=list)
    note: str = ""


def normalize(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Map NFC characters back to original Unicode code-point offsets."""
    boundaries = [0]
    for char in text:
        boundaries.append(boundaries[-1] + len(unicodedata.normalize("NFD", char)))
    output: list[str] = []
    positions: list[tuple[int, int]] = []
    cursor = 0
    for char in unicodedata.normalize("NFC", text):
        end = cursor + len(unicodedata.normalize("NFD", char))
        if not char.isspace():
            output.append(char.translate(QUOTE_MARKS))
            positions.append((bisect_right(boundaries, cursor) - 1, bisect_left(boundaries, end)))
        cursor = end
    return "".join(output), positions


def locate(start: int, end: int, paragraphs: tuple[Paragraph, ...]) -> Location:
    return Location(
        start=start,
        end=end,
        paragraph_start=next(p.number for p in paragraphs if p.start <= start < p.end),
        paragraph_end=next(p.number for p in paragraphs if p.start <= end - 1 < p.end),
    )


def differences(quote: str, original: str) -> list[dict[str, object]]:
    return [
        {"operation": tag, "quote_range": [a, b], "source_range": [c, d], "source": original[c:d]}
        for tag, a, b, c, d in SequenceMatcher(None, quote, original).get_opcodes()
        if tag != "equal"
    ]


def check_quote(
    quote: str,
    text: str,
    paragraphs: tuple[Paragraph, ...],
    normalized: str,
    positions: list[tuple[int, int]],
) -> QuoteResult:
    found: list[Location] = []
    cursor = 0
    while len(found) < 11:
        index = text.find(quote, cursor)
        if index < 0:
            break
        found.append(locate(index, index + len(quote), paragraphs))
        cursor = index + 1
    if found:
        return QuoteResult(
            quote=quote,
            status="exact",
            locations=found[:10],
            requires_review=len(found) > 1,
            note=(
                "위치가 여러 곳입니다." + (" 앞 10곳만 표시합니다." if len(found) > 10 else "")
                if len(found) > 1
                else ""
            ),
        )
    needle, _ = normalize(quote)
    cursor = 0
    while needle and len(found) < 11:
        index = normalized.find(needle, cursor)
        if index < 0:
            break
        start, end = positions[index][0], positions[index + len(needle) - 1][1]
        if normalize(text[start:end])[0] == needle:
            found.append(locate(start, end, paragraphs))
        cursor = index + 1
    if found:
        location = found[0]
        original = text[location.start : location.end]
        return QuoteResult(
            quote=quote,
            status="orthography",
            locations=found[:10],
            requires_review=True,
            suggestion=original,
            differences=differences(quote, original),
            note="NFC·공백·따옴표 표기가 다릅니다. 원문과 차이를 확인하세요.",
        )
    # shortcut: fuzzy search proposes one aligned window, never an automatic correction.
    # Upgrade candidate search only when teacher examples show missed useful suggestions.
    match = SequenceMatcher(None, needle, normalized).find_longest_match()
    if len(needle) >= 4 and match.size >= max(3, len(needle) * 0.6) and match.b >= match.a:
        start = match.b - match.a
        end = min(len(normalized), start + len(needle))
        candidate = normalized[start:end]
        if SequenceMatcher(None, needle, candidate).ratio() >= 0.75:
            raw_start, raw_end = positions[start][0], positions[end - 1][1]
            original = text[raw_start:raw_end]
            return QuoteResult(
                quote=quote,
                status="mismatch",
                locations=[locate(raw_start, raw_end, paragraphs)],
                requires_review=True,
                suggestion=original,
                differences=differences(quote, original),
                note="가까운 후보이며 위치를 확정한 결과가 아닙니다. 교정 후 재검증하세요.",
            )
    return QuoteResult(
        quote=quote,
        status="not_found",
        requires_review=True,
        note="원문에서 확인하지 못했습니다. 짧은 인용·다른 판본·누락을 확인하세요.",
    )


def verify_quote(
    request: VerifyRequest, editions: tuple[Edition, ...] = ()
) -> Envelope[QuoteResult]:
    source = Source(name="교사 제공 텍스트")
    rights: Literal["public_domain", "protected", "unknown"] = "unknown"
    text = request.source_text
    if text is None:
        source = Source(name="검수 원문 목록")
        try:
            edition = select_edition(
                editions, work_id=request.work_id, edition_id=request.edition_id
            )
            source, rights = edition.manifest.source, edition.manifest.copyright
            if edition.manifest.sha256 != request.source_hash:
                raise SourceError(
                    "source_changed", "원문 해시가 다릅니다. get_passage로 다시 조회하세요."
                )
        except SourceError as error:
            return Envelope(
                source=source,
                copyright=rights,
                error=ErrorInfo(code=error.code, message=str(error)),
                note=str(error),
            )
        text = edition.text
        paragraphs = edition.paragraphs
    else:
        paragraphs = split_paragraphs(text)
    if request.quotes is None:
        return Envelope(
            source=source,
            copyright=rights,
            error=ErrorInfo(
                code="draft_not_supported", message="현재 quotes[]로 인용을 전달하세요."
            ),
            note="초안 추출은 별도 단계에서 추가합니다.",
        )
    normalized, positions = normalize(text)
    results = [check_quote(q, text, paragraphs, normalized, positions) for q in request.quotes]
    verified = all(r.status == "exact" and not r.requires_review for r in results)
    return Envelope(
        items=results,
        source=source,
        copyright=rights,
        note=(
            "제출한 모든 인용이 원문과 문자 그대로 일치합니다. 초안 전체를 검사한 것은 아닙니다."
            if verified
            else "검토가 필요한 인용이 있습니다. 차이·후보·미확인 결과를 확인하세요."
        ),
    )
