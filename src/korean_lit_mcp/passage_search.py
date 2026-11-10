"""Bounded phrase search over a selected edition, with unchanged raw context."""

from typing import Annotated, Literal

from pydantic import Field

from korean_lit_mcp.contracts import Digest, Envelope, ErrorInfo, Identifier, Input, Source, Text
from korean_lit_mcp.sources import Edition, SourceError, select_edition
from korean_lit_mcp.verification import Location, find_locations, normalize


class FindPassageRequest(Input):
    work_id: Identifier
    edition_id: Identifier
    query: Annotated[Text, Field(max_length=200)]
    match_mode: Literal["exact", "orthography"] = "exact"
    context_chars: int = Field(default=80, ge=0, le=300)
    limit: int = Field(default=3, ge=1, le=5)


class PassageMatch(Input):
    location: Location
    text: str
    match_kind: Literal["exact", "orthography"]
    requires_review: bool
    context_start: int
    context_end: int
    context_text: str


class PassageSearchResult(Envelope[PassageMatch]):
    work_id: str
    edition_id: str
    source_hash: Digest | None = None
    has_more: bool = False
    omitted_oversized_matches: int = 0
    omitted_budget_matches: int = 0


def find_passage(request: FindPassageRequest, editions: tuple[Edition, ...]) -> PassageSearchResult:
    ids = {"work_id": request.work_id, "edition_id": request.edition_id}
    try:
        edition = select_edition(editions, **ids)
    except SourceError as error:
        return PassageSearchResult(
            work_id=request.work_id,
            edition_id=request.edition_id,
            source=Source(name="검수 원문 목록"),
            error=ErrorInfo(code=error.code, message=str(error)),
        )
    text, manifest = edition.text, edition.manifest
    if request.match_mode == "exact":
        locations = find_locations(request.query, text, edition.paragraphs)
    else:
        normalized, positions = normalize(text)
        locations = find_locations(
            normalize(request.query)[0],
            text,
            edition.paragraphs,
            normalized=normalized,
            positions=positions,
        )
    eligible = [p for p in locations if p.end - p.start <= 600]
    items = []
    for location in eligible[: request.limit]:
        raw = text[location.start : location.end]
        start = max(0, location.start - request.context_chars)
        end = min(len(text), location.end + request.context_chars)
        items.append(
            PassageMatch(
                location=location,
                text=raw,
                match_kind="exact" if raw == request.query else "orthography",
                requires_review=len(locations) > 1 or raw != request.query,
                context_start=start,
                context_end=end,
                context_text=text[start:end],
            )
        )
    result = PassageSearchResult(
        work_id=request.work_id,
        edition_id=request.edition_id,
        items=items,
        source=manifest.source,
        copyright=manifest.copyright,
        retrieved_at=manifest.reviewed_at,
        source_hash=manifest.sha256,
        has_more=len(eligible) > request.limit or len(locations) == 11,
        omitted_oversized_matches=len(locations) - len(eligible),
        note="선택 판본 안의 구절 검색입니다. 위치는 0부터 시작하며 끝은 제외합니다. "
        "원문 text와 문맥은 변형하지 않았습니다. 표기 차이·여러 위치는 검토하세요. "
        "문맥 경계는 코드포인트 기준입니다. 600자를 넘는 일치 후보는 생략 건수를 표시합니다. "
        "검색한 앞 11곳을 기준으로 반환합니다. 응답 예산 생략 건수도 확인하고 "
        "문맥을 줄여 재시도하세요. 0건을 판본 전체의 부재로 해석하지 마세요. " + manifest.note,
    )

    # Leave room for MCP's text + structured result duplication and JSON escaping.
    while result.items and len(result.model_dump_json().encode("utf-8")) > 6000:
        result.items.pop()
        result.omitted_budget_matches += 1
        result.has_more = True
    return result
