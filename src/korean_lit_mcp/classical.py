"""Public ITKC search results; snippets are not verified editions or full texts."""

import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Annotated, Literal

import httpx
from pydantic import Field, HttpUrl

from korean_lit_mcp.cache import CacheBusy, PublicCache
from korean_lit_mcp.contracts import Envelope, Input, Source, Text
from korean_lit_mcp.sources import SourceError
from korean_lit_mcp.work_identity import WorkIdentity, classify_record, find_candidates

SOURCE = Source(name="한국고전종합DB", url=HttpUrl("https://db.itkc.or.kr/etc/openAPI?type=page1"))


class ClassicalSearchRequest(Input):
    query: Annotated[Text, Field(max_length=200)]
    collection: Literal["classic", "anthology", "corpus"] = "classic"
    target: Literal["body", "title"] = "body"
    limit: int = Field(default=10, ge=1, le=20)


class ClassicalSearchResult(Envelope[dict[str, object]]):
    work_candidates: list[WorkIdentity] = Field(default_factory=list)


def parse_response(raw: bytes) -> tuple[list[dict[str, str]], int]:
    try:
        text = raw.decode("utf-8-sig")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("Unsafe XML")
        root = ET.fromstring(text)
        if root.tag != "response":
            raise ValueError("Unexpected root")
        total = int(root.findtext("./header/field[@name='totalCount']", ""))
        records = []
        for doc in root.findall("./result/doc"):
            record = {}
            for field in doc.findall("field"):
                name = field.get("name")
                if not name or name in record:
                    raise ValueError("Invalid field")
                record[name] = "".join(field.itertext())
            if not re.fullmatch(r"ITKC_[A-Za-z0-9_]+", record.get("자료ID", "")):
                raise ValueError("Invalid ID")
            if not record.get("기사명") or not record.get("검색필드"):
                raise ValueError("Missing result fields")
            records.append(record)
        if total < 0 or (total > 0 and not records) or len(records) > total:
            raise ValueError("Unexpected count")
        return records, total
    except (ValueError, ET.ParseError) as error:
        raise SourceError(
            "upstream_invalid", "한국고전종합DB 응답 형식을 확인할 수 없습니다."
        ) from error


class ClassicalLibrary:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.endpoint = os.environ.get("ITKC_API_URL")
        if self.endpoint:
            url = httpx.URL(self.endpoint)
            if url.scheme != "https" or not url.host or url.userinfo or url.query or url.fragment:
                raise ValueError("ITKC_API_URL requires an HTTPS URL without credentials or query.")
        self.transport = transport
        self.cache = PublicCache()
        logging.getLogger("httpx").setLevel(logging.WARNING)

    async def search(self, request: ClassicalSearchRequest) -> ClassicalSearchResult:
        endpoint = self.endpoint
        if not endpoint:
            raise SourceError("upstream_not_configured", "ITKC_API_URL 설정이 필요합니다.")
        section = {"classic": "GO", "anthology": "MO", "corpus": "KP"}[request.collection]
        section += "_BD" if request.target == "body" else "_GS"

        async def fetch() -> bytes:
            try:
                async with httpx.AsyncClient(transport=self.transport, timeout=10) as client:
                    async with client.stream(
                        "GET",
                        endpoint,
                        params={
                            "secId": section,
                            "keyword": request.query,
                            "start": 0,
                            "rows": request.limit,
                        },
                    ) as response:
                        if response.status_code == 429:
                            raise SourceError(
                                "upstream_limit", "기관 검색 한도입니다. 잠시 후 재시도하세요."
                            )
                        response.raise_for_status()
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > 2 * 1024 * 1024:
                                raise SourceError(
                                    "upstream_invalid", "기관 응답 크기 제한을 넘습니다."
                                )
                records, total = parse_response(bytes(body))
                if len(records) > request.limit:
                    raise SourceError("upstream_invalid", "기관 응답 건수가 요청 상한을 넘습니다.")
                return json.dumps(
                    {
                        "records": records,
                        "total": total,
                        "retrieved_at": datetime.now(UTC).isoformat(),
                    }
                ).encode()
            except httpx.HTTPError as error:
                raise SourceError(
                    "upstream_unavailable", "한국고전종합DB에 연결하지 못했습니다."
                ) from error

        try:
            raw = await self.cache.get((section, request.query, str(request.limit)), fetch, ttl=300)
        except (CacheBusy, TimeoutError) as error:
            raise SourceError(
                "upstream_busy", "기관 검색이 지연되고 있습니다. 재시도하세요."
            ) from error
        data = json.loads(raw)
        candidates = find_candidates(request.query)
        items: list[dict[str, object]] = []
        for record in data["records"]:
            items.append(
                {
                    "match_kind": classify_record(record["기사명"], record["검색필드"], candidates),
                    "identity_status": "unconfirmed",
                    "record_id": record["자료ID"],
                    "title": record["기사명"],
                    "book_title": record.get("서명", ""),
                    "author": record.get("저자", ""),
                    "document_author": record.get("저자", ""),
                    "author_role": "source_record_author",
                    "work_author": None,
                    "search_target": request.target,
                    "volume": record.get("권차명", ""),
                    "snippet": record["검색필드"],
                    "is_excerpt": True,
                    "available_text": False,
                    "url": "https://db.itkc.or.kr/dir/item?itemId="
                    + section[:2]
                    + "&dataId="
                    + record["자료ID"],
                    "source": SOURCE.model_dump(mode="json"),
                }
            )
        return ClassicalSearchResult(
            items=items,
            work_candidates=candidates,
            source=SOURCE,
            retrieved_at=datetime.fromisoformat(data["retrieved_at"]),
            note=f"전체 {data['total']}건 중 첫 {len(items)}건. 검색필드는 기관의 검색 발췌이며 "
            "강조 마크업이 포함될 수 있습니다. 작품 전문·검수 판본이 아니며 "
            "get_passage의 작품 ID로 사용할 수 없습니다. "
            "document_author는 기관 레코드의 저자이며 검색한 작품의 작가를 뜻하지 않습니다. "
            "author는 같은 값의 호환 필드입니다. work_author는 확인되지 않아 null입니다. "
            + (
                "기사명 검색 결과이며 제목 일치가 작품 원문 확인을 뜻하지 않습니다. "
                if request.target == "title"
                else "본문 언급 검색 결과이며 작품 자체를 찾은 것이 아닙니다. "
            )
            + "work_candidates는 검색어에 대한 참고 메타데이터이며 "
            "레코드·판본 식별 확정이 아닙니다. "
            "title_candidate는 제목 후보, body_mention은 문자열 언급, "
            "unconfirmed_search_match는 알려진 이칭과 불일치, unclassified는 미등록 검색어입니다. "
            "동음 한자·동명이작을 자동 결합하지 않습니다. 캐시 최대 5분.",
        )
