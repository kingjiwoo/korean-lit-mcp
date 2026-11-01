import hashlib

from korean_lit_mcp.contracts import (
    Envelope,
    ErrorInfo,
    PassageRequest,
    SearchContext,
    SearchRequest,
    Source,
)
from korean_lit_mcp.sources import Edition, SourceError, search_key, select_edition


def search_works(
    request: SearchRequest, editions: tuple[Edition, ...]
) -> Envelope[dict[str, object]]:
    term = search_key(request.query)
    matches = []
    for edition in editions:
        m = edition.manifest
        if not term or (term not in search_key(m.title) and term not in search_key(m.author)):
            continue
        if request.author is not None and search_key(request.author) not in search_key(m.author):
            continue
        if request.year_from is not None and m.year < request.year_from:
            continue
        if request.year_to is not None and m.year > request.year_to:
            continue
        matches.append(
            {
                "work_id": m.work_id,
                "edition_id": m.edition_id,
                "title": m.title,
                "author": m.author,
                "year": m.year,
                "edition": m.edition,
                "source": m.source.model_dump(mode="json"),
                "retrieved_at": m.reviewed_at.isoformat(),
                "copyright": m.copyright,
                "rights_url": str(m.rights_url),
                "available_text": m.copyright == "public_domain",
            }
        )
    return Envelope(
        items=matches[: request.limit],
        source=Source(name="검수 원문 목록"),
        copyright="public_domain" if matches else "unknown",
        search_context=SearchContext(
            request=request.model_dump(mode="json"),
            scope="reviewed_catalogue",
            outcome="matches" if matches else "no_matches" if editions else "empty_catalogue",
            reviewed_work_count=len({e.manifest.work_id for e in editions}),
            reviewed_edition_count=len(editions),
        ),
        note=(
            "검수 원문 목록에서 제목·작가를 검색했습니다."
            if matches
            else "검수 원문 목록 자체가 비어 있습니다. "
            "확인한 판본이나 교사 제공 본문을 source_text로 대조하세요. 추정 복원하지 마세요."
            if not editions
            else "검수 원문 목록에서 일치하는 제목·작가를 찾지 못했습니다. "
            "이 검색의 0건은 전체 목록이 비었거나 다른 자료원에 작품이 없다는 뜻이 아닙니다. "
            "확인한 판본을 확보하거나 교사가 제공한 본문을 source_text로 대조하세요. "
            "누락된 옛한글을 모델 기억이나 추정으로 복원해 원문으로 사용하지 마세요."
        ),
    )


def get_passage(
    request: PassageRequest, editions: tuple[Edition, ...]
) -> Envelope[dict[str, object]]:
    try:
        edition = select_edition(
            editions,
            work_id=request.work_id,
            title=request.title,
            author=request.author,
            edition_id=request.edition_id,
        )
        end = request.end if request.end is not None else len(edition.paragraphs)
        if request.start > len(edition.paragraphs) or end > len(edition.paragraphs):
            raise SourceError("invalid_range", "요청한 문단·행 범위가 원문 주소 범위를 벗어납니다.")
    except SourceError as error:
        return Envelope(
            source=Source(name="검수 원문 목록"),
            error=ErrorInfo(code=error.code, message=str(error)),
            note=str(error)
            + " 원문을 반환하지 않았습니다. 검색어·작가·판본·요청 범위를 확인하세요. "
            "검수 판본을 확보하거나 교사가 제공한 본문을 source_text로 대조하세요. "
            "모델 기억·추정 복원을 원문으로 사용하지 마세요.",
        )
    m = edition.manifest
    paragraphs = [
        {
            "number": p.number,
            "start": p.start,
            "end": p.end,
            "text": p.text,
            "sha256": hashlib.sha256(p.text.encode("utf-8")).hexdigest(),
        }
        for p in edition.paragraphs[request.start - 1 : end]
    ]
    return Envelope(
        items=[
            {
                "work_id": m.work_id,
                "edition_id": m.edition_id,
                "title": m.title,
                "author": m.author,
                "edition": m.edition,
                "source_hash": m.sha256,
                "rights_url": str(m.rights_url),
                "rights_note": m.rights_note,
                "address_basis": m.segmentation,
                "paragraphs": paragraphs,
            }
        ],
        source=m.source,
        copyright=m.copyright,
        retrieved_at=m.reviewed_at,
        note=m.note,
    )
