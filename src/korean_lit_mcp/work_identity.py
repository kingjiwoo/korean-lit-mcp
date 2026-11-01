"""Reviewed discovery metadata, never an assertion that an ITKC record is a work."""

import html
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl

from korean_lit_mcp.sources import search_key


class WorkIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity_id: str
    title: str
    aliases: tuple[str, ...]
    attested_in: tuple[str, ...]
    attribution: str
    reference: HttpUrl
    reviewed_on: str = "2026-11-01"


# shortcut: three reviewed discovery entries; extend only with cited metadata review.
WORKS = (
    WorkIdentity(
        identity_id="discovery-gyuwonga",
        title="규원가",
        aliases=("규원가", "閨怨歌", "원부사", "怨夫詞", "怨婦詞", "원부가", "怨婦歌"),
        attested_in=("고금가곡", "교주가곡집", "순오지"),
        attribution="작자 미상. 허난설헌 귀속과 무옥 귀속 등 이견이 있어 확정하지 않음.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0007270"),
    ),
    WorkIdentity(
        identity_id="discovery-samiingok",
        title="사미인곡",
        aliases=("사미인곡", "思美人曲"),
        attested_in=("송강집", "송강가사", "문청공유사"),
        attribution="정철. 이 메타데이터는 같은 제목의 검색 문헌에 작가를 부여하지 않음.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0025613"),
    ),
    WorkIdentity(
        identity_id="discovery-honggildongjeon",
        title="홍길동전",
        aliases=("홍길동전", "홍길동젼", "洪吉童傳", "위도왕전", "韋島王傳"),
        attested_in=("택당집 별집 권15 산록: 작품 저술 언급, 현전 판본과 동일성 미확정",),
        attribution="허균이 지었다고 전함. 작자 논란과 이본 차이가 있어 판본별 확인 필요.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0063994"),
    ),
)


def find_candidates(query: str) -> list[WorkIdentity]:
    term = search_key(query)
    return [work for work in WORKS if term in {search_key(alias) for alias in work.aliases}]


def classify_record(
    title: str, snippet: str, candidates: list[WorkIdentity]
) -> Literal["title_candidate", "body_mention", "unconfirmed_search_match", "unclassified"]:
    if not candidates:
        return "unclassified"
    aliases = {search_key(alias) for work in candidates for alias in work.aliases}
    if search_key(title) in aliases:
        return "title_candidate"
    # Only ITKC emphasis tags are removed, and only from the comparison copy.
    body = search_key(html.unescape(re.sub(r"</?em\b[^>]*>", "", snippet, flags=re.I)))
    if any(alias in body for alias in aliases):
        return "body_mention"
    return "unconfirmed_search_match"
