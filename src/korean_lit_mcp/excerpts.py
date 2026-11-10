"""Compare declared ranges and edits; never infer editorial intent or alter sources."""

from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from korean_lit_mcp.contracts import (
    Digest,
    Envelope,
    ErrorInfo,
    Input,
    Quote,
    Source,
    TextReference,
)
from korean_lit_mcp.references import ReferenceText, resolve_reference
from korean_lit_mcp.sources import Edition, SourceError
from korean_lit_mcp.verification import Location, differences, locate

Marker = Annotated[str, Field(pattern=r"^\[[0-9]{1,3}\]$")]


class EditRules(Input):
    ignore_whitespace: bool = False
    drop_note_markers: Annotated[list[Marker], Field(max_length=20)] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_markers(self) -> Self:
        if len(set(self.drop_note_markers)) != len(self.drop_note_markers):
            raise ValueError("Declare each removed marker only once.")
        return self


class SourceRange(Input):
    start: int = Field(ge=0, le=50000)
    end: int = Field(ge=1, le=50000)

    @model_validator(mode="after")
    def bounded_range(self) -> Self:
        if not 0 < self.end - self.start <= 4000:
            raise ValueError("Source ranges must be nonempty and at most 4000 code points.")
        return self


class ExcerptSegment(SourceRange):
    quote: Quote


class ExcerptRequest(TextReference):
    segments: Annotated[list[ExcerptSegment], Field(min_length=1, max_length=10)]
    rules: EditRules = Field(default_factory=EditRules)

    @model_validator(mode="after")
    def ordered_segments(self) -> Self:
        if any(a.end > b.start for a, b in pairwise(self.segments)):
            raise ValueError("Segments must be ordered and non-overlapping.")
        if (
            sum(s.end - s.start for s in self.segments) > 10000
            or sum(len(s.quote) for s in self.segments) > 10000
        ):
            raise ValueError("Selected source and quotation totals must each be at most 10000.")
        return self


class RemovedRange(Input):
    start: int
    end: int
    kind: Literal["whitespace", "declared_marker"]
    text: str


class EditedText(Input):
    text: str
    positions: list[int]
    removed: list[RemovedRange]
    removed_count: int
    changes_truncated: bool


def apply_edits(text: str, offset: int, rules: EditRules) -> EditedText:
    kept: list[str] = []
    positions: list[int] = []
    removed: list[RemovedRange] = []
    cursor = 0
    count = 0
    while cursor < len(text):
        marker = next((m for m in rules.drop_note_markers if text.startswith(m, cursor)), None)
        end = cursor + 1
        kind: Literal["whitespace", "declared_marker"] | None = None
        if marker is not None:
            end = cursor + len(marker)
            kind = "declared_marker"
        elif rules.ignore_whitespace and text[cursor].isspace():
            while end < len(text) and text[end].isspace():
                end += 1
            kind = "whitespace"
        if kind is None:
            kept.append(text[cursor])
            positions.append(offset + cursor)
        else:
            count += 1
            if len(removed) < 20:
                removed.append(
                    RemovedRange(
                        start=offset + cursor, end=offset + end, kind=kind, text=text[cursor:end]
                    )
                )
        cursor = end
    return EditedText(
        text="".join(kept),
        positions=positions,
        removed=removed,
        removed_count=count,
        changes_truncated=count > 20,
    )


class SegmentResult(Input):
    location: Location
    original: str
    quote: str
    source_comparison: EditedText
    quote_comparison: EditedText
    status: Literal["exact", "edited_match", "mismatch"]
    requires_review: bool
    differences: list[dict[str, object]]
    differences_count: int
    differences_truncated: bool


class ExcerptResult(Envelope[SegmentResult]):
    reference_basis: Literal["reviewed_edition", "supplied_text"]
    work_id: str | None = None
    edition_id: str | None = None
    source_hash: Digest | None = None
    rules: EditRules
    omissions: list[Location] = Field(default_factory=list)
    all_raw_exact: bool = False
    all_match_rules: bool = False


def check_reference(reference: ReferenceText, request: TextReference) -> None:
    if request.source_hash is not None and request.source_hash != reference.source_hash:
        raise SourceError("source_changed", "원문 해시가 다릅니다. 원문을 다시 조회하세요.")


def compare_segment(
    segment: ExcerptSegment, reference: ReferenceText, rules: EditRules
) -> SegmentResult:
    if segment.end > len(reference.text):
        raise SourceError("invalid_range", "지정한 원문 범위가 본문을 벗어납니다.")
    original = reference.text[segment.start : segment.end]
    source_copy = apply_edits(original, segment.start, rules)
    quote_copy = apply_edits(segment.quote, 0, rules)
    status: Literal["exact", "edited_match", "mismatch"] = "mismatch"
    if original == segment.quote:
        status = "exact"
    elif source_copy.text and source_copy.text == quote_copy.text:
        status = "edited_match"
    delta = differences(quote_copy.text, source_copy.text)
    return SegmentResult(
        location=locate(segment.start, segment.end, reference.paragraphs),
        original=original,
        quote=segment.quote,
        source_comparison=source_copy,
        quote_comparison=quote_copy,
        status=status,
        requires_review=status != "exact",
        differences=delta[:20],
        differences_count=len(delta),
        differences_truncated=len(delta) > 20,
    )


def verify_excerpt(request: ExcerptRequest, editions: tuple[Edition, ...] = ()) -> ExcerptResult:
    source = Source(
        name="교사 제공 텍스트" if request.source_text is not None else "검수 원문 목록"
    )
    result = ExcerptResult(
        source=source,
        reference_basis="supplied_text" if request.source_text is not None else "reviewed_edition",
        work_id=request.work_id,
        edition_id=request.edition_id,
        rules=request.rules,
    )
    result.note = "지정한 인용만 대조하며 문학 해석·정답·생략 적절성은 판정하지 않습니다. " + (
        "제공 문자열 기준이며 정본·출처를 인증하지 않습니다. "
        if request.source_text is not None
        else ""
    )
    try:
        reference = resolve_reference(request, editions)
        result.source, result.copyright = reference.source, reference.copyright
        check_reference(reference, request)
        items = [compare_segment(s, reference, request.rules) for s in request.segments]
        omissions = [
            locate(a.end, b.start, reference.paragraphs)
            for a, b in pairwise(request.segments)
            if a.end < b.start
        ]
    except SourceError as error:
        result.error = ErrorInfo(code=error.code, message=str(error))
        result.note = str(error) + " " + result.note
        return result
    result.items, result.omissions = items, omissions
    result.source_hash = reference.source_hash
    result.all_raw_exact = all(s.status == "exact" for s in items)
    result.all_match_rules = all(s.status != "mismatch" for s in items)
    result.note += (
        "지정한 원문 구간과 인용만 대조했습니다. edited_match는 명시한 편집 규칙 적용 후의 "
        "일치이며 원문 그대로의 일치가 아닙니다. 표지의 각주 의미·생략 적절성·문학 해석·정답은 "
        "판정하지 않습니다. 비교 positions는 원문/인용 코드포인트 좌표이며 differences는 "
        "비교 문자열 좌표입니다. 삭제·차이 상세는 각 20건까지, 전체 건수·잘림 여부를 확인하세요."
    )
    return result
