"""Literary discovery uses reviewed identities; remote bibliography stays unconfirmed."""

import json
from datetime import datetime

from korean_lit_mcp.contracts import Envelope, SearchContext, SearchRequest, Source
from korean_lit_mcp.sources import Edition, search_key
from korean_lit_mcp.work_identity import WORKS, find_candidates


def discover_work(
    request: SearchRequest, editions: tuple[Edition, ...]
) -> Envelope[dict[str, object]] | None:
    candidates = find_candidates(request.query, request.author)
    if not candidates:
        candidates = [
            w
            for w in WORKS
            if w.author is not None
            and search_key(request.query) == search_key(w.author)
            and (request.author is None or search_key(request.author) == search_key(w.author))
        ]
    supplied_ids = {e.manifest.work_id for e in editions}
    candidates = [w for w in candidates if not supplied_ids.intersection(w.reviewed_work_ids)]
    if not candidates:
        return None
    return Envelope(
        items=[
            {
                "kind": "work_candidate",
                "identity_id": w.identity_id,
                "title": w.title,
                "author": w.author,
                "attribution": w.attribution,
                "author_filter_status": "unconfirmed"
                if request.author and w.author is None
                else "matched"
                if request.author
                else "not_requested",
                "available_text": False,
                "text_status": "unavailable",
                "reference": str(w.reference),
                "next_searches": [
                    {"query": q, "mode": "catalogue", "nl_category": "old_books", "limit": 3}
                    for q in (w.catalogue_queries or (w.title,))[:2]
                ],
                "relationship": "source_volume_candidate"
                if w.catalogue_queries
                else "bibliography_search",
            }
            for w in candidates[: request.limit]
        ],
        source=Source(name="검수 작품 식별 목록"),
        retrieved_at=min(
            datetime.fromisoformat(w.reviewed_on + "T00:00:00+00:00") for w in candidates
        ),
        search_context=SearchContext(
            request=request.model_dump(mode="json"),
            scope="literary_discovery",
            outcome="work_identified",
            reviewed_work_count=len({e.manifest.work_id for e in editions}),
            reviewed_edition_count=len(editions),
        ),
        note="미확보 후보 항목의 작품은 식별했지만 제공할 검수 원문은 없습니다. "
        "next_searches는 수록 문헌/서지 탐색 경로이며 해당 판본의 수록을 확정하지 않습니다. "
        "연도 조건은 제공 판본의 발행연도에 적용되며 이 후보의 충족 여부는 미확인입니다. "
        "작가 미상·귀속 이견 후보는 요청한 작가 조건의 충족을 확인하지 않습니다. "
        "원문을 추정 복원하지 마세요.",
    )


def summarize_bibliography(items: list[dict[str, object]]) -> tuple[list[dict[str, object]], int]:
    summaries = []
    omitted = 0
    for item in items:
        if item.get("material_type") in {"음악자료", "멀티미디어", "영상자료", "기사"} or str(
            item.get("kdc", "")
        ).startswith("6"):
            omitted += 1
            continue
        brief: dict[str, object] = {
            k: item[k]
            for k in (
                "record_id",
                "work_id",
                "title",
                "author",
                "publisher",
                "year",
                "material_type",
                "url",
                "original_url",
                "original_type",
                "access_code",
                "access_note",
                "source",
                "copyright",
                "available_text",
            )
            if k in item
        }
        brief.update(
            kind="bibliographic_candidate", identity_status="unconfirmed", work_author=None
        )
        brief["author_role"] = "source_record_author"
        for field, limit in (("title", 200), ("author", 100), ("publisher", 150)):
            if isinstance(value := brief.get(field), str) and len(value) > limit:
                brief[field] = value[:limit] + "…"
                brief["summary_truncated"] = True
        brief["document_author"] = brief.get("author")
        # Keep rights/access notes intact; omit an oversized summary with an explicit count.
        if len(json.dumps(brief, ensure_ascii=False).encode()) > 1800:
            omitted += 1
            continue
        summaries.append(brief)
    return summaries, omitted
