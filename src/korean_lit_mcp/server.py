from fastmcp import FastMCP

from korean_lit_mcp.catalogue import SOURCE, NationalLibrary
from korean_lit_mcp.classical import SOURCE as ITKC_SOURCE
from korean_lit_mcp.classical import ClassicalLibrary, ClassicalSearchRequest
from korean_lit_mcp.contracts import (
    Envelope,
    ErrorInfo,
    PassageRequest,
    SearchContext,
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
    classical = ClassicalLibrary()
    server = FastMCP(
        "korean-lit-mcp",
        instructions=(
            "인용 전 get_passage로 판본과 원문을 확보하고 작성 후 verify_quote로 검증하세요. "
            "조회한 판본과 source_hash를 검증 요청에 전달하세요. "
            "미검증 범위를 검증 완료라고 표시하지 마세요. "
            "출처와 판본을 결과물에 표시하세요. "
            "고전 작품 찾기는 search_classical_text의 target=title로 먼저 탐색하고, "
            "관련 기록은 target=body로 구분해 검색하세요. "
            "document_author와 호환 필드 author는 검색 문헌의 저자이며 작품 작가가 아닙니다. "
            "search_context.request의 실제 검색어를 사용자가 요청한 작품과 대조하세요. "
            "0건을 빈 검수 목록이나 모든 자료원의 작품 부재로 해석하지 마세요. "
            "작품 원문을 확인하지 못했으면 검색 발췌·관련 기록만 찾았다고 알리고, "
            "확인한 판본 또는 교사가 제공한 본문을 요청하세요. "
            "모델 기억이나 추정으로 누락된 옛한글·원문을 복원하지 마세요. "
            "자료 작성은 클라이언트에서 하고, 모든 지문·해설 인용을 제출해 대조한 후 "
            "수정한 인용을 재검증하세요. "
            "제공 본문과의 일치는 정본 인증이나 문항 정답 검증이 아닙니다."
        ),
        mask_error_details=True,
        middleware=[ToolMetrics()],
        auth=None,
    )

    @server.tool(name="search_works", annotations={"readOnlyHint": True})
    async def search(request: SearchRequest) -> Envelope[dict[str, object]]:
        """작품 제목·작가로 검수된 원문을 찾을 때 사용합니다.

        판본별 ID와 본문 제공 여부, 실제 요청·검색 범위·검수 목록 크기를 반환합니다.
        0건은 이 조건의 미일치입니다. 빈 목록·전체 자료원 미수록으로 해석하지 마세요.
        원문 미확보 시 확인된 판본 또는 교사 제공 본문으로 대조하세요.
        """
        local = search_works(request, editions)
        if catalogue is None or len(local.items) >= request.limit:
            return local
        assert local.search_context is not None
        local.search_context.scope = "reviewed_catalogue_and_nl"
        try:
            remote = await catalogue.search(request)
        except SourceError as error:
            local.search_context.upstream_error = ErrorInfo(code=error.code, message=str(error))
            local.search_context.outcome = "partial_results" if local.items else "upstream_error"
            if local.items:
                local.note += " 기관 서지 검색 실패: " + str(error)
                return local
            return Envelope(
                source=SOURCE,
                error=ErrorInfo(code=error.code, message=str(error)),
                search_context=local.search_context,
                note=local.note + " 기관 검색 실패: " + str(error),
            )
        local.items.extend(remote.items[: request.limit - len(local.items)])
        local.source = Source(name="검수 원문 목록·국립중앙도서관")
        local.copyright = "unknown" if remote.items else local.copyright
        local.retrieved_at = min(local.retrieved_at, remote.retrieved_at)
        local.search_context.outcome = "matches" if local.items else "no_matches"
        local.note += " " + remote.note
        return local

    @server.tool(name="search_classical_text", annotations={"readOnlyHint": True})
    async def classical_search(request: ClassicalSearchRequest) -> Envelope[dict[str, object]]:
        """한국고전종합DB에서 고전원문·문집총간·고전총간의 본문/기사명을 검색합니다.

        작품 찾기는 target=title, 본문 언급 찾기는 target=body를 명시하세요.
        기본값 body는 기존 호출 호환을 유지합니다. 제목 일치가 작품 원문 확인은 아닙니다.
        실제 검색어·컬렉션·대상은 search_context.request로 확인하세요.
        document_author와 author는 기관 레코드 저자이며 작품 작가는 미확인입니다.
        기관 검색 발췌와 자료 링크를 반환합니다. 전문 조회나 판본 검증이 아닙니다.
        """
        try:
            return await classical.search(request)
        except SourceError as error:
            return Envelope(
                source=ITKC_SOURCE,
                error=ErrorInfo(code=error.code, message=str(error)),
                search_context=SearchContext(
                    request=request.model_dump(mode="json"), scope="itkc", outcome="upstream_error"
                ),
                note="기관 검색에 실패했습니다. 자료 0건이나 원문 부재가 아닙니다.",
            )

    @server.tool(name="get_passage", annotations={"readOnlyHint": True})
    def passage(request: PassageRequest) -> Envelope[dict[str, object]]:
        """인용 작성 전에 만료 판본의 원문을 확보할 때 사용합니다.

        원문 미확보 시 확인한 판본이나 교사 제공 본문으로 대조하고 추정 복원하지 마세요.
        원문을 변형 없이 반환합니다. 문단·행 주소는 1부터 시작하고 끝을 포함합니다.
        """
        return get_passage(request, editions)

    @server.tool(name="verify_quote", annotations={"readOnlyHint": True})
    def verify(request: VerifyRequest) -> VerificationResult:
        """문제·자료 작성 후 인용을 원문과 대조할 때 사용합니다.

        조회한 작품·판본·해시 또는 교사가 제공한 source_text를 사용합니다.
        표기 차이와 교정 후보를 자동 통과시키지 말고 확인·재검증하세요.
        source_text는 전달된 문자열 기준이며 실제 정본 인증이 아닙니다.
        제출·추출한 인용만 대조하며 문학 해석·문항 정답·초안 전체를 검증하지 않습니다.
        """
        return verify_quote(request, editions)

    return server
