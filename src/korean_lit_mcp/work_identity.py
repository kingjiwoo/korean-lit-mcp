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
    author: str | None = None
    aliases: tuple[str, ...]
    catalogue_queries: tuple[str, ...] = ()
    reviewed_work_ids: tuple[str, ...] = ()
    attested_in: tuple[str, ...]
    attribution: str
    reference: HttpUrl
    reviewed_on: str = "2026-11-01"


# Discovery entries are cited metadata, not bindings to provider records or editions.
WORKS = (
    WorkIdentity(
        identity_id="discovery-gyuwonga",
        reviewed_work_ids=("gongu-13313635",),
        title="규원가",
        aliases=("규원가", "閨怨歌", "원부사", "怨夫詞", "怨婦詞", "원부가", "怨婦歌"),
        attested_in=("고금가곡", "교주가곡집", "순오지"),
        attribution="작자 미상. 허난설헌 귀속과 무옥 귀속 등 이견이 있어 확정하지 않음.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0007270"),
    ),
    WorkIdentity(
        identity_id="discovery-samiingok",
        reviewed_work_ids=("gongu-13313606",),
        catalogue_queries=("송강가사",),
        title="사미인곡",
        author="정철",
        aliases=("사미인곡", "思美人曲"),
        attested_in=("송강집", "송강가사", "문청공유사"),
        attribution="정철. 이 메타데이터는 같은 제목의 검색 문헌에 작가를 부여하지 않음.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0025613"),
    ),
    WorkIdentity(
        identity_id="discovery-honggildongjeon",
        reviewed_work_ids=("classical-honggildongjeon",),
        title="홍길동전",
        aliases=("홍길동전", "홍길동젼", "洪吉童傳", "위도왕전", "韋島王傳"),
        attested_in=("택당집 별집 권15 산록: 작품 저술 언급, 현전 판본과 동일성 미확정",),
        attribution="허균이 지었다고 전함. 작자 논란과 이본 차이가 있어 판본별 확인 필요.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0063994"),
    ),
    WorkIdentity(
        identity_id="discovery-cheongsanbyeolgok",
        reviewed_work_ids=("aks-E0056472",),
        catalogue_queries=("악장가사",),
        title="청산별곡",
        aliases=("청산별곡", "靑山別曲", "青山別曲"),
        attested_in=("악장가사: 전문", "시용향악보: 제1연과 곡조"),
        attribution="고려가요, 작자 미상. 수록 문헌 후보와 특정 판본의 확인은 구분함.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0056472"),
        reviewed_on="2026-11-04",
    ),
    WorkIdentity(
        identity_id="discovery-gwandong-jeongcheol",
        reviewed_work_ids=("gongu-13313590",),
        catalogue_queries=("송강가사", "협률대성"),
        title="관동별곡",
        author="정철",
        aliases=("관동별곡", "關東別曲"),
        attested_in=("송강가사", "협률대성"),
        attribution="정철의 1580년 가사. 안축의 동명 경기체가와 다른 작품.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0004779"),
        reviewed_on="2026-11-04",
    ),
    WorkIdentity(
        identity_id="discovery-gwandong-anchuk",
        catalogue_queries=("근재집",),
        title="관동별곡",
        author="안축",
        aliases=("관동별곡", "關東別曲"),
        attested_in=("근재집 권2",),
        attribution="안축의 1330년 경기체가. 정철의 동명 가사와 다른 작품.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0004778"),
        reviewed_on="2026-11-04",
    ),
    WorkIdentity(
        identity_id="discovery-guunmong",
        title="구운몽",
        author="김만중",
        aliases=("구운몽", "九雲夢"),
        attested_in=(),
        attribution="김만중의 고전소설. 국문·한문과 이본 차이는 판본별 확인 필요.",
        reference=HttpUrl("https://encykorea.aks.ac.kr/Article/E0005948"),
        reviewed_on="2026-11-04",
    ),
)


def find_candidates(query: str, author: str | None = None) -> list[WorkIdentity]:
    term = search_key(query)
    return [
        work
        for work in WORKS
        if term in {search_key(alias) for alias in work.aliases}
        and (author is None or work.author is None or search_key(author) == search_key(work.author))
    ]


def classify_record(
    title: str, snippet: str, candidates: list[WorkIdentity], *, target: Literal["title", "body"]
) -> Literal[
    "title_candidate", "title_mention", "body_mention", "unconfirmed_search_match", "unclassified"
]:
    if not candidates:
        return "unclassified"
    aliases = {search_key(alias) for work in candidates for alias in work.aliases}
    if search_key(title) in aliases:
        return "title_candidate"
    if any(alias in search_key(title) for alias in aliases):
        return "title_mention"
    if target == "title":
        return "unconfirmed_search_match"
    # Only ITKC emphasis tags are removed, and only from the comparison copy.
    body = search_key(html.unescape(re.sub(r"</?em\b[^>]*>", "", snippet, flags=re.I)))
    if any(alias in body for alias in aliases):
        return "body_mention"
    return "unconfirmed_search_match"
