"""Optional National Library metadata search; never supplies literary bodies."""

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import httpx
from pydantic import HttpUrl

from korean_lit_mcp.cache import CacheBusy, PublicCache
from korean_lit_mcp.contracts import Envelope, SearchRequest, Source
from korean_lit_mcp.sources import SourceError, search_key

ENDPOINT = "https://www.nl.go.kr/NL/search/openApi/search.do"
SOURCE = Source(
    name="국립중앙도서관", url=HttpUrl("https://www.nl.go.kr/NL/contents/N31101030700.do")
)


def parse_response(raw: bytes) -> tuple[list[dict[str, str]], int]:
    try:
        text = raw.decode("utf-8-sig")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise SourceError("upstream_invalid", "기관 API의 XML 선언을 허용하지 않습니다.")
        root = ET.fromstring(text)
        error_code = root.findtext(".//error_code")
        if error_code:
            code = "upstream_auth" if error_code in {"010", "011"} else "upstream_error"
            if error_code == "012":
                code = "upstream_limit"
            raise SourceError(code, f"국립중앙도서관 API 오류 코드 {error_code}.")
        total_text = root.findtext(".//total")
        if total_text is None:
            raise ValueError("Missing total")
        total = int(total_text)
        records = [{child.tag: child.text or "" for child in item} for item in root.iter("item")]
        if total < 0 or (total > 0 and not records):
            raise ValueError("Unexpected record shape")
        if any(not r.get("title_info") or not r.get("control_no") for r in records):
            raise ValueError("Missing catalogue fields")
        return records, total
    except (ET.ParseError, ValueError) as error:
        raise SourceError("upstream_invalid", "기관 API 응답 형식을 확인할 수 없습니다.") from error


class NationalLibrary:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.transport = transport
        self.cache = PublicCache()
        # httpx INFO logs include query-string API keys.
        logging.getLogger("httpx").setLevel(logging.WARNING)

    async def search(self, request: SearchRequest) -> Envelope[dict[str, object]]:
        async def fetch() -> bytes:
            params = {
                "key": self.api_key,
                "apiType": "xml",
                "srchTarget": "total",
                "kwd": request.query,
                "pageNum": "1",
                "pageSize": "20",
            }
            try:
                async with httpx.AsyncClient(
                    transport=self.transport or httpx.AsyncHTTPTransport(retries=1),
                    timeout=httpx.Timeout(10, connect=3),
                ) as client:
                    async with client.stream("GET", ENDPOINT, params=params) as response:
                        if response.status_code == 429:
                            retry_after = response.headers.get("retry-after", "")
                            delay = (
                                f" {int(retry_after)}초 후 재시도하세요."
                                if retry_after.isascii()
                                and retry_after.isdecimal()
                                and len(retry_after) <= 6
                                else " 잠시 후 재시도하세요."
                            )
                            raise SourceError("upstream_limit", "기관 호출 한도입니다." + delay)
                        response.raise_for_status()
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > 2 * 1024 * 1024:
                                raise SourceError(
                                    "upstream_invalid", "기관 API 응답이 크기 제한을 넘습니다."
                                )
                records, total = parse_response(bytes(body))
                return json.dumps(
                    {
                        "records": records,
                        "total": total,
                        "retrieved_at": datetime.now(UTC).isoformat(),
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
            except httpx.HTTPError as error:
                raise SourceError(
                    "upstream_unavailable", "국립중앙도서관 API에 연결하지 못했습니다."
                ) from error

        try:
            raw = await self.cache.get(
                ("nl-v1", request.query),
                fetch,
                ttl=lambda value: 60 if not json.loads(value)["records"] else 30 * 86400,
            )
        except (CacheBusy, TimeoutError) as error:
            raise SourceError(
                "upstream_busy", "기관 검색이 지연되고 있습니다. 잠시 후 재시도하세요."
            ) from error
        cached = json.loads(raw)
        items: list[dict[str, object]] = []
        for record in cached["records"]:
            author = record.get("author_info", "")
            if request.author is not None and search_key(request.author) not in search_key(author):
                continue
            year_match = re.search(r"\d{4}", record.get("pub_year_info", ""))
            year = int(year_match[0]) if year_match else None
            if request.year_from is not None and (year is None or year < request.year_from):
                continue
            if request.year_to is not None and (year is None or year > request.year_to):
                continue
            items.append(
                {
                    "work_id": "nl-" + record["control_no"],
                    "title": record["title_info"],
                    "author": author,
                    "year": year,
                    "kdc": record.get("kdc_code_1s"),
                    "copyright": "unknown",
                    "available_text": False,
                    "source": SOURCE.model_dump(mode="json"),
                    "retrieved_at": cached["retrieved_at"],
                }
            )
        return Envelope(
            items=items[: request.limit],
            source=SOURCE,
            retrieved_at=datetime.fromisoformat(cached["retrieved_at"]),
            note=(
                "기관 검색 첫 20건에 작가·연도 필터를 적용했습니다. "
                "서지 캐시는 최대 30일이며 retrieved_at은 최초 조회 시각입니다. "
                "기관 서지 ID는 서버의 검수 원문 ID와 다릅니다. "
                "원문 유무를 본문 제공 허락으로 간주하지 않습니다."
                + (" 검색 결과 500건 상한에 도달했습니다." if cached["total"] >= 500 else "")
            ),
        )
