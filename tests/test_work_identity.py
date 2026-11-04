from korean_lit_mcp.work_identity import classify_record, find_candidates


def test_same_title_works_remain_separate():
    works = find_candidates("關東別曲")
    assert {work.author for work in works} == {"정철", "안축"}
    assert len({work.identity_id for work in works}) == 2
    assert [work.author for work in find_candidates("관동별곡", "정철")] == ["정철"]
    assert find_candidates("관동별곡", "합성 타작가") == []


def test_unknown_attribution_is_preserved():
    assert find_candidates("규원가")[0].author is None
    assert find_candidates("청산별곡")[0].author is None
    assert find_candidates("九雲夢")[0].author == "김만중"


def test_title_snippet_cannot_be_called_body_evidence():
    candidates = find_candidates("사미인곡")
    assert classify_record("思美人曲", "발췌", candidates, target="title") == "title_candidate"
    assert classify_record("聞思美人曲有感", "발췌", candidates, target="title") == "title_mention"
    assert (
        classify_record("합성 기사", "思美人曲", candidates, target="title")
        == "unconfirmed_search_match"
    )
    assert (
        classify_record("합성 기사", "<em>思美人曲</em>", candidates, target="body")
        == "body_mention"
    )
    assert (
        classify_record("九原可", "九原可", find_candidates("규원가"), target="body")
        == "unconfirmed_search_match"
    )
