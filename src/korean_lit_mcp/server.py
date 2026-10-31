from fastmcp import FastMCP

from korean_lit_mcp.catalogue import SOURCE, NationalLibrary
from korean_lit_mcp.contracts import (
    Envelope,
    ErrorInfo,
    PassageRequest,
    SearchRequest,
    Source,
    VerifyRequest,
)
from korean_lit_mcp.metrics import ToolMetrics
from korean_lit_mcp.passages import get_passage, search_works
from korean_lit_mcp.sources import Edition, SourceError
from korean_lit_mcp.verification import VerificationResult, verify_quote


def create_server(*, editions: tuple[Edition, ...] = (), nl_api_key: str | None = None) -> FastMCP:
    catalogue = NationalLibrary(nl_api_key) if nl_api_key else None
    server = FastMCP(
        "korean-lit-mcp",
        instructions=(
            "인용 전 get_passage로 판본과 원문을 확보하고 작성 후 verify_quote로 검증하세요. "
            "조회한 판본과 source_hash를 검증 요청에 전달하세요. "
            "미검증 범위를 검증 완료라고 표시하지 마세요. "
            "출처와 판본을 결과물에 표시하세요."
        ),
        mask_error_details=True,
        middleware=[ToolMetrics()],
        auth=None,
    )

    @server.tool(name="search_works", annotations={"readOnlyHint": True})
    async def search(request: SearchRequest) -> Envelope[dict[str, object]]:
        """작품 제목·작가로 검수된 원문을 찾을 때 사용합니다.

        판본별 ID와 본문 제공 여부를 반환합니다.
        """
        local = search_works(request, editions)
        if catalogue is None or len(local.items) >= request.limit:
            return local
        try:
            remote = await catalogue.search(request)
        except SourceError as error:
            if local.items:
                local.note += " 기관 서지 검색 실패: " + str(error)
                return local
            return Envelope(
                source=SOURCE, error=ErrorInfo(code=error.code, message=str(error)), note=str(error)
            )
        local.items.extend(remote.items[: request.limit - len(local.items)])
        local.source = Source(name="검수 원문 목록·국립중앙도서관")
        local.copyright = "unknown" if remote.items else local.copyright
        local.retrieved_at = min(local.retrieved_at, remote.retrieved_at)
        local.note += " " + remote.note
        return local

    @server.tool(name="get_passage", annotations={"readOnlyHint": True})
    def passage(request: PassageRequest) -> Envelope[dict[str, object]]:
        """인용 작성 전에 만료 판본의 원문을 확보할 때 사용합니다.

        원문을 변형 없이 반환합니다. 문단·행 주소는 1부터 시작하고 끝을 포함합니다.
        """
        return get_passage(request, editions)

    @server.tool(name="verify_quote", annotations={"readOnlyHint": True})
    def verify(request: VerifyRequest) -> VerificationResult:
        """문제·자료 작성 후 인용을 원문과 대조할 때 사용합니다.

        조회한 작품·판본·해시 또는 교사가 제공한 source_text를 사용합니다.
        표기 차이와 교정 후보를 자동 통과시키지 말고 확인·재검증하세요.
        """
        return verify_quote(request, editions)

    return server
