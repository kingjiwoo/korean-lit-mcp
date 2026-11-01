import json
import unicodedata
from pathlib import Path

import pytest
from pydantic import ValidationError

from korean_lit_mcp.grammar import GrammarRequest, load_grammar, lookup_grammar, term_key
from korean_lit_mcp.sources import SourceError


@pytest.fixture
def entries():
    return load_grammar(Path("data/grammar"))


@pytest.mark.parametrize(
    ("term", "period", "expected"),
    [
        ("  주격조사  ", "modern", "modern-subject-particle"),
        ("변이형", "modern", "modern-allomorph"),
        ("히읗종성체언", "middle", "middle-h-final-noun"),
        ("거듭적기", "early_modern", "early-modern-double-spelling"),
    ],
)
def test_reviewed_terms_and_aliases(entries, term, period, expected):
    result = lookup_grammar(GrammarRequest(term=term, period=period), entries)
    assert result.items[0]["entry_id"] == expected
    assert result.items[0]["sources"][0]["license"] == "CC-BY-SA-2.0-KR"
    assert result.copyright == "protected"
    assert "임의 문장 분석" in result.note


def test_periods_are_separate_even_for_the_same_term(entries):
    for period in ("modern", "middle"):
        result = lookup_grammar(GrammarRequest(term="객체 높임법", period=period), entries)
        assert [item["entry_id"] for item in result.items] == [f"{period}-object-honorific"]
    missing = lookup_grammar(GrammarRequest(term="객체 높임법", period="early_modern"), entries)
    assert not missing.items and missing.error is None
    assert "현상 자체가 없다는 뜻은 아닙니다" in missing.note


def test_exact_alias_precedes_partial_matches_and_limit_is_applied(entries):
    exact = entries[0].model_copy(update={"entry_id": "z-exact", "aliases": ["어미"]})
    result = lookup_grammar(
        GrammarRequest(term="어미", period="modern", limit=1), (*entries, exact)
    )
    assert [item["entry_id"] for item in result.items] == ["z-exact"]


def test_unicode_search_does_not_rewrite_source_forms(entries):
    assert term_key("ß") != term_key("ss")
    decomposed = unicodedata.normalize("NFD", "종결 어미")
    assert lookup_grammar(GrammarRequest(term=decomposed, period="modern"), entries).items
    assert not lookup_grammar(GrammarRequest(term="어ㆍ간", period="modern"), entries).items
    result = lookup_grammar(GrammarRequest(term="중철", period="early_modern"), entries)
    assert result.items[0]["examples"][0]["text"] == "말이 → 말미"
    assert result.items[0]["examples"][0]["kind"] == "source_example"


def test_responses_do_not_mutate_the_loaded_catalogue(entries):
    request = GrammarRequest(term="어간", period="modern")
    result = lookup_grammar(request, entries)
    result.items[0]["explanation"] = "private changed response"
    assert lookup_grammar(request, entries).items[0]["explanation"] != "private changed response"


@pytest.mark.parametrize(
    "changes",
    [
        {"term": " "},
        {"term": "가" * 101},
        {"period": "ancient"},
        {"limit": 0},
        {"limit": 11},
        {"limit": "1"},
        {"source_text": "private passage is not accepted"},
    ],
)
def test_request_bounds_and_lookup_only_contract(changes):
    with pytest.raises(ValidationError):
        GrammarRequest(**({"term": "어간", "period": "modern"} | changes))


@pytest.mark.parametrize("damage", ["sources", "license", "example", "duplicate", "empty"])
def test_invalid_data_never_becomes_an_empty_success(tmp_path, damage):
    data = json.loads(Path("data/grammar/entries.json").read_text())
    if damage == "sources":
        data[0]["sources"] = []
    elif damage == "license":
        data[0]["sources"][0]["license"] = "unknown"
    elif damage == "example":
        data[0]["examples"][0]["kind"] = "source_example"
        data[0]["examples"][0]["source_url"] = "https://example.invalid/unrelated"
    elif damage == "duplicate":
        data.append(data[0])
    else:
        data = []
    (tmp_path / "entries.json").write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(SourceError, match="문법") as error:
        load_grammar(tmp_path)
    assert error.value.code == "invalid_grammar_data"


def test_unavailable_or_oversized_data_fails_loudly(tmp_path):
    with pytest.raises(SourceError, match="문법"):
        load_grammar(tmp_path)
    (tmp_path / "entries.json").write_bytes(b" " * 1_000_001)
    with pytest.raises(SourceError) as error:
        load_grammar(tmp_path)
    assert error.value.code == "file_too_large"


def test_symlink_cannot_load_data_outside_the_bundle(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("[]")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "entries.json").symlink_to(outside)
    with pytest.raises(SourceError, match="경로"):
        load_grammar(bundle)
