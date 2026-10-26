import hashlib

from korean_lit_mcp.contracts import Envelope, ErrorInfo, PassageRequest, SearchRequest, Source
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
        note=(
            "검수 원문 목록에서 제목·작가를 검색했습니다."
            if matches
            else "검수 원문 목록에서 일치하는 제목·작가를 찾지 못했습니다. 검색어를 확인하세요."
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
            note=str(error),
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
