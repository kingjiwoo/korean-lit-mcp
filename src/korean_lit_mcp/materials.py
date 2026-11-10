"""A request-scoped report over explicit citation spans, not semantic item grading."""

from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from korean_lit_mcp.contracts import (
    Digest,
    Envelope,
    ErrorInfo,
    Identifier,
    Input,
    Source,
    Text,
    TextReference,
)
from korean_lit_mcp.excerpts import (
    EditRules,
    ExcerptSegment,
    SegmentResult,
    SourceRange,
    check_reference,
    compare_segment,
)
from korean_lit_mcp.references import resolve_reference
from korean_lit_mcp.sources import Edition, SourceError


class MaterialCitation(SourceRange):
    source_start: int = Field(ge=0, le=50000)
    source_end: int = Field(ge=1, le=50000)

    @model_validator(mode="after")
    def citation_bounds(self) -> Self:
        if self.end - self.start > 2000 or not 0 < self.source_end - self.source_start <= 4000:
            raise ValueError(
                "Citations allow at most 2000 block characters and 4000 source characters."
            )
        return self


class MaterialBlock(Input):
    block_id: Identifier
    kind: Literal["passage", "option", "explanation"]
    text: Annotated[Text, Field(max_length=30000)]
    citations: Annotated[list[MaterialCitation], Field(max_length=20)] = Field(default_factory=list)

    @model_validator(mode="after")
    def citation_spans(self) -> Self:
        if any(c.end > len(self.text) for c in self.citations):
            raise ValueError("Citation block ranges must be inside the actual block text.")
        if any(not self.text[c.start : c.end].strip() for c in self.citations):
            raise ValueError("Citation block ranges must contain non-whitespace text.")
        if any(a.end > b.start for a, b in pairwise(self.citations)):
            raise ValueError("Block citation spans must be ordered and non-overlapping.")
        return self


class MaterialRequest(TextReference):
    blocks: Annotated[list[MaterialBlock], Field(min_length=1, max_length=10)]
    rules: EditRules = Field(default_factory=EditRules)

    @model_validator(mode="after")
    def report_bounds(self) -> Self:
        if len({b.block_id for b in self.blocks}) != len(self.blocks):
            raise ValueError("Block IDs must be unique.")
        citations = [c for b in self.blocks for c in b.citations]
        if sum(len(b.text) for b in self.blocks) > 30000 or len(citations) > 20:
            raise ValueError("At most 30000 block characters and 20 citations are allowed.")
        if (
            sum(c.source_end - c.source_start for c in citations) > 10000
            or sum(c.end - c.start for c in citations) > 10000
        ):
            raise ValueError("Selected source and citation totals must each be at most 10000.")
        return self


class BlockRange(Input):
    start: int
    end: int


class CitationReport(Input):
    block_range: BlockRange
    comparison: SegmentResult


class BlockReport(Input):
    block_id: str
    kind: Literal["passage", "option", "explanation"]
    citations: list[CitationReport]
    unverified_ranges: list[BlockRange]


class MaterialResult(Envelope[BlockReport]):
    reference_basis: Literal["reviewed_edition", "supplied_text"]
    work_id: str | None = None
    edition_id: str | None = None
    source_hash: Digest | None = None
    rules: EditRules
    checked_count: int = 0
    review_required_count: int = 0
    unverified_character_count: int = 0
    all_submitted_raw_exact: bool = False


def review_material(request: MaterialRequest, editions: tuple[Edition, ...] = ()) -> MaterialResult:
    result = MaterialResult(
        source=Source(
            name="교사 제공 텍스트" if request.source_text is not None else "검수 원문 목록"
        ),
        reference_basis="supplied_text" if request.source_text is not None else "reviewed_edition",
        work_id=request.work_id,
        edition_id=request.edition_id,
        rules=request.rules,
        note="명시한 블록 인용 영역만 대조했습니다. 나머지 영역은 미검증입니다. "
        "블록 내 여러 인용의 연결 순서·생략 적절성은 검증하지 않으며 연결 발췌는 verify_excerpt로 "
        "별도 대조하세요. 문학 해석·정답·초안 전체·제공 본문의 정본 여부는 인증하지 않습니다.",
    )
    items = []
    try:
        reference = resolve_reference(request, editions)
        result.source, result.copyright = reference.source, reference.copyright
        check_reference(reference, request)
        for block in request.blocks:
            citations = []
            gaps = []
            cursor = 0
            for c in block.citations:
                if c.start > cursor:
                    gaps.append(BlockRange(start=cursor, end=c.start))
                segment = ExcerptSegment(
                    start=c.source_start, end=c.source_end, quote=block.text[c.start : c.end]
                )
                citations.append(
                    CitationReport(
                        block_range=BlockRange(start=c.start, end=c.end),
                        comparison=compare_segment(segment, reference, request.rules),
                    )
                )
                cursor = c.end
            if cursor < len(block.text):
                gaps.append(BlockRange(start=cursor, end=len(block.text)))
            items.append(
                BlockReport(
                    block_id=block.block_id,
                    kind=block.kind,
                    citations=citations,
                    unverified_ranges=gaps,
                )
            )
    except SourceError as error:
        result.error = ErrorInfo(code=error.code, message=str(error))
        result.note = str(error) + " " + result.note
        return result
    result.items = items
    result.source_hash = reference.source_hash
    comparisons = [c.comparison for b in items for c in b.citations]
    result.checked_count = len(comparisons)
    result.review_required_count = sum(c.requires_review for c in comparisons)
    result.unverified_character_count = sum(
        r.end - r.start for b in items for r in b.unverified_ranges
    )
    result.all_submitted_raw_exact = bool(comparisons) and all(
        c.status == "exact" for c in comparisons
    )
    return result
