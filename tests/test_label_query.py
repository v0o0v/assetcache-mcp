"""M4 — label_query 파서 (자연어 라벨 부울 → ParsedLabelQuery).

문법 요약:
    expr     = or_expr
    or_expr  = and_expr ('OR' and_expr)*
    and_expr = not_expr (('AND' | implicit_and) not_expr)*
    not_expr = 'NOT'? atom
    atom     = '(' or_expr ')' | axis_label | bare_label | free_token
    axis_label = IDENT ':' IDENT
    bare_label = IDENT     -- LabelRegistry 에서 axis 자동 매칭

키워드 `AND`/`OR`/`NOT` 은 대문자 전체 일치만. 그 외는 라벨 또는 free_token.
DNF 정규화 후 순수 AND → labels_all (NOT 은 labels_none), 순수 OR → labels_any.
혼합은 v1 한계 — UnsupportedExpression.
모호 bare label (같은 token 이 여러 axis) → AmbiguousLabel + 후보.
"""

from __future__ import annotations

import pytest


# ── 결정적 LabelRegistry fixture ─────────────────────────────────────


class _FakeLabelRegistry:
    """파서가 의존하는 부분 (`list_labels(with_description=False)`) 만 구현.

    실제 LabelRegistry 와 같은 시그니처를 갖되, in-memory dict 로 빠르게 회답.
    각 테스트는 라벨 분포를 자유롭게 조립 가능.
    """

    def __init__(self, axis_labels: dict[str, list[str]]) -> None:
        # {axis: [labels]}
        self._by_axis = {k: list(v) for k, v in axis_labels.items()}

    def list_labels(self, axis=None, *, enabled_only=True, with_description=False):
        if axis is not None:
            return list(self._by_axis.get(axis, []))
        merged: list[str] = []
        for ax in sorted(self._by_axis):
            merged.extend(self._by_axis[ax])
        return merged

    def list_axes(self) -> list[str]:
        return sorted(self._by_axis)

    # 파서가 axis 역인덱스를 직접 쓰면 유용 (만약 그 인터페이스를 채택했다면).
    def axes_for_label(self, label: str) -> list[str]:
        return sorted(ax for ax, lbls in self._by_axis.items() if label in lbls)


@pytest.fixture
def registry_simple():
    """`hero` `dark` `pixel_art` 라벨 — 각각 axis 1 개씩 (모호 없음)."""
    return _FakeLabelRegistry({
        "category": ["hero", "ui", "background"],
        "style": ["pixel_art", "vector_cartoon"],
        "sound_mood": ["bright", "dark", "calm"],
        "sound_use": ["combat", "menu", "ambient"],
    })


@pytest.fixture
def registry_ambiguous():
    """`dark` 가 `sound_mood` + `sprite_palette` 양쪽에 있음 — 모호 케이스."""
    return _FakeLabelRegistry({
        "sound_mood": ["bright", "dark", "calm"],
        "sprite_palette": ["dark", "vibrant", "pastel"],
        "category": ["hero", "ui"],
    })


@pytest.fixture
def registry_korean():
    """한국어 라벨 매칭 테스트용."""
    return _FakeLabelRegistry({
        "분위기": ["밝음", "어두움"],
        "장르": ["오케스트라", "칩튠"],
    })


# ── 테스트 본체 ──────────────────────────────────────────────────────


def test_empty_input_returns_empty_parsed(registry_simple):
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("", registry_simple)
    assert parsed.labels_all == []
    assert parsed.labels_any == []
    assert parsed.labels_none == []
    assert parsed.free_text == ""


def test_single_bare_label_resolves_to_axis(registry_simple):
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("hero", registry_simple)
    # 단일 atom → labels_all 1 개 (axis 자동 매칭)
    assert len(parsed.labels_all) == 1
    f = parsed.labels_all[0]
    assert (f.axis, f.label) == ("category", "hero")
    assert parsed.labels_any == []
    assert parsed.labels_none == []
    assert parsed.free_text == ""


def test_axis_label_explicit_form_matches_exact(registry_simple):
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("sound_mood:dark", registry_simple)
    assert len(parsed.labels_all) == 1
    f = parsed.labels_all[0]
    assert (f.axis, f.label) == ("sound_mood", "dark")


def test_and_two_atoms_to_labels_all(registry_simple):
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("hero AND pixel_art", registry_simple)
    assert {(f.axis, f.label) for f in parsed.labels_all} == {
        ("category", "hero"),
        ("style", "pixel_art"),
    }
    assert parsed.labels_any == []
    assert parsed.labels_none == []


def test_or_two_atoms_to_labels_any(registry_simple):
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("bright OR dark", registry_simple)
    # bright/dark 모두 sound_mood — 모호 없음 (sound_mood 에만 있다고 가정한 simple registry)
    assert parsed.labels_all == []
    assert {(f.axis, f.label) for f in parsed.labels_any} == {
        ("sound_mood", "bright"),
        ("sound_mood", "dark"),
    }
    assert parsed.labels_none == []


def test_not_atom_to_labels_none(registry_simple):
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("NOT calm", registry_simple)
    assert parsed.labels_all == []
    assert parsed.labels_any == []
    assert {(f.axis, f.label) for f in parsed.labels_none} == {
        ("sound_mood", "calm"),
    }


def test_implicit_and_between_adjacent_atoms(registry_simple):
    """공백 사이 atom 은 AND 로 묵시 처리 — `hero pixel_art` == `hero AND pixel_art`."""
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("hero pixel_art", registry_simple)
    assert {(f.axis, f.label) for f in parsed.labels_all} == {
        ("category", "hero"),
        ("style", "pixel_art"),
    }


def test_nested_parens_pure_and(registry_simple):
    """`(hero AND pixel_art)` — 단일 그룹 그대로 labels_all."""
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("(hero AND pixel_art)", registry_simple)
    assert {(f.axis, f.label) for f in parsed.labels_all} == {
        ("category", "hero"),
        ("style", "pixel_art"),
    }


def test_nested_parens_pure_or(registry_simple):
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("(bright OR dark OR calm)", registry_simple)
    assert {(f.axis, f.label) for f in parsed.labels_any} == {
        ("sound_mood", "bright"),
        ("sound_mood", "dark"),
        ("sound_mood", "calm"),
    }


def test_mixed_and_or_raises_unsupported_expression(registry_simple):
    """`(hero AND pixel_art) OR background` — v1 한계."""
    from gah.core.label_query import UnsupportedExpression, parse_label_query

    with pytest.raises(UnsupportedExpression):
        parse_label_query("(hero AND pixel_art) OR background", registry_simple)


def test_unknown_token_goes_to_free_text(registry_simple):
    """등록되지 않은 토큰 — 파서가 free_text 로 빼낸다."""
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("hero zelda_quest_iv", registry_simple)
    # hero → labels_all, zelda_quest_iv → free_text
    assert {(f.axis, f.label) for f in parsed.labels_all} == {("category", "hero")}
    assert "zelda_quest_iv" in parsed.free_text


def test_ambiguous_bare_label_raises_with_candidates(registry_ambiguous):
    """`dark` 가 sound_mood + sprite_palette 양쪽 → AmbiguousLabel + 후보."""
    from gah.core.label_query import AmbiguousLabel, parse_label_query

    with pytest.raises(AmbiguousLabel) as ei:
        parse_label_query("dark", registry_ambiguous)
    assert ei.value.label == "dark"
    assert set(ei.value.candidates) >= {"sound_mood", "sprite_palette"}


def test_uppercase_only_keywords_lowercase_treated_as_label(registry_simple):
    """`and` (소문자) 는 키워드가 아니라 토큰. simple registry 에 `and` 라벨은 없으므로 free_text 로."""
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("hero and pixel_art", registry_simple)
    # hero / pixel_art 는 라벨이지만 `and` (소문자) 가 키워드가 아니므로
    # 묵시 AND 가 양쪽에 적용된다 → labels_all 에 hero + pixel_art,
    # `and` 자체는 free_text.
    assert {(f.axis, f.label) for f in parsed.labels_all} == {
        ("category", "hero"),
        ("style", "pixel_art"),
    }
    assert "and" in parsed.free_text


def test_korean_label_matches(registry_korean):
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query("어두움 AND 오케스트라", registry_korean)
    assert {(f.axis, f.label) for f in parsed.labels_all} == {
        ("분위기", "어두움"),
        ("장르", "오케스트라"),
    }


def test_quoted_string_token_preserved(registry_simple):
    """`"dark cave"` 따옴표 안 토큰은 단일 free_token — 라벨 매칭 없이 free_text 로."""
    from gah.core.label_query import parse_label_query

    parsed = parse_label_query('"dark cave"', registry_simple)
    assert parsed.labels_all == []
    assert parsed.labels_any == []
    # 따옴표 내용을 free_text 에 보존 (따옴표 자체는 제거되어도 됨)
    assert "dark cave" in parsed.free_text


def test_precedence_not_then_and_then_or_or_unsupported(registry_simple):
    """`a OR b AND NOT c` — 일반 우선순위 `(a) OR (b AND NOT c)` 가 정상.

    v1 의 DNF 한계로 OR-of-(AND-with-NOT) 는 UnsupportedExpression 으로
    raise 가 정상. 만약 단순화 가능한 케이스라면 정확 매핑이어도 OK 단,
    혼합 표현임을 인지하는 것이 핵심.
    """
    from gah.core.label_query import UnsupportedExpression, parse_label_query

    with pytest.raises(UnsupportedExpression):
        parse_label_query("bright OR dark AND NOT calm", registry_simple)
