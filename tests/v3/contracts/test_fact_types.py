"""L0 §4 dotted glob language, staging overlap and ownership conflicts."""

from collections import deque
from dataclasses import FrozenInstanceError, fields
from enum import StrEnum
from functools import lru_cache
from itertools import product

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts import fact_types
from custom_components.heima.v3.contracts.fact_types import (
    FactTypeClaim,
    fact_type_matches,
    fact_type_patterns_overlap,
    validate_fact_type,
    validate_fact_type_claims,
)


@pytest.mark.parametrize(
    "pattern,name,expected",
    [
        ("lighting.*door*", "lighting.pippodoor", True),
        ("lighting.*door*", "lighting.doorpippo", True),
        ("lighting.*door*", "lighting.door", True),
        ("lighting.*door*", "lighting.room.lifecycle", False),
        ("lighting.*.lifecycle", "lighting.room.lifecycle", True),
        ("lighting.*", "lighting.a.b", False),
        ("*", "presence", True),
        ("*", "a.b", False),
        ("a*b", "ab", True),
        ("a*b", "axxb", True),
        ("a*b", "axxc", False),
        ("**", "a", True),
        ("a**b", "ab", True),
        ("a*", "a", True),
        ("*a", "a", True),
        ("a?", "a?", True),
        ("a?", "ab", False),
        ("[ab]", "a", False),
        ("[ab]", "[ab]", True),
        ("a\\b", "a\\b", True),
        ("a\\b", "ab", False),
        ("A", "a", False),
        ("é", "e\u0301", False),
        (" a ", " a ", True),
        ("😀*", "😀\ue000", True),
    ],
)
def test_complete_literal_segment_matching(pattern, name, expected):
    assert fact_type_matches(pattern, name) is expected


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("a*", "*b", True),
        ("a", "b", False),
        ("*a", "b*", True),
        ("a*", "b*", False),
        ("*a", "*b", False),
        ("*", "*", True),
        ("**", "***", True),
        ("a*b", "a*c", False),
        ("a*b", "a*x*b", True),
        ("lighting.*", "lighting.*.lifecycle", False),
        ("lighting.*.*", "lighting.*.lifecycle", True),
        ("x.a.y", "x.b.y", False),
        ("x.a.y", "x.a.z", False),
        ("x.a.y", "z.a.y", False),
        ("x.a.y", "x.a.y", True),
        ("a?", "a*", True),
        ("[ab]", "b*", False),
        ("e\u0301*", "é*", False),
        ("a*b", "a*b", True),
    ],
)
def test_overlap_decision_table(left, right, expected):
    assert fact_type_patterns_overlap(left, right) is expected
    assert fact_type_patterns_overlap(right, left) is expected


@pytest.mark.parametrize("same_owner,same_kind,overlap", list(product((False, True), repeat=3)))
def test_claim_conflict_decision_table(same_owner, same_kind, overlap):
    claims = (
        FactTypeClaim("lighting.*", "owner", "state"),
        FactTypeClaim(
            "lighting.kitchen" if overlap else "heating.*",
            "owner" if same_owner else "other",
            "state" if same_kind else "event",
        ),
    )
    if overlap and not (same_owner and same_kind):
        with pytest.raises(ValueError):
            validate_fact_type_claims(claims)
    else:
        validate_fact_type_claims(claims)


@pytest.mark.parametrize("name", ["", ".a", "a.", "a..b"])
@pytest.mark.parametrize("target", ["concrete", "pattern", "match"])
def test_empty_segment_boundaries(name, target):
    with pytest.raises(ValueError):
        if target == "concrete":
            validate_fact_type(name)
        elif target == "pattern":
            FactTypeClaim(name, "owner", "state")
        else:
            fact_type_matches("*", name)


@pytest.mark.parametrize("name", ["*", "a*b", "a.*.b"])
def test_concrete_identifiers_reject_every_wildcard(name):
    with pytest.raises(ValueError):
        validate_fact_type(name)
    with pytest.raises(ValueError):
        fact_type_matches("*", name)


class Name(StrEnum):
    VALUE = "state"


@pytest.mark.parametrize("invalid", [None, 1, True, Name.VALUE])
def test_primitive_string_boundary(invalid):
    with pytest.raises(TypeError):
        validate_fact_type(invalid)
    with pytest.raises(TypeError):
        FactTypeClaim(invalid, "owner", "state")
    with pytest.raises(TypeError):
        FactTypeClaim("x", invalid, "state")
    with pytest.raises(TypeError):
        FactTypeClaim("x", "owner", invalid)


@pytest.mark.parametrize("kind", ["", "STATE", "occurrence"])
def test_closed_emission_vocabulary(kind):
    with pytest.raises(ValueError):
        FactTypeClaim("x", "owner", kind)


@pytest.mark.parametrize("field", ["fact_type_pattern", "owner_id"])
def test_unencodable_claim_metadata_rejects(field):
    args = dict(fact_type_pattern="x", owner_id="owner", emission_kind="state")
    args[field] = "\ud800"
    with pytest.raises(ValueError):
        FactTypeClaim(**args)


def test_claim_envelope_and_immutability():
    claim = FactTypeClaim(" A .*", " owner ", "event")
    assert [f.name for f in fields(claim)] == ["fact_type_pattern", "owner_id", "emission_kind"]
    assert claim.fact_type_pattern == " A .*" and claim.owner_id == " owner "
    assert not hasattr(claim, "__dict__")
    with pytest.raises(FrozenInstanceError):
        claim.owner_id = "other"
    assert len({claim, FactTypeClaim(" A .*", " owner ", "event")}) == 1


def test_empty_single_and_equivalent_duplicate_claims():
    validate_fact_type_claims(())
    c = FactTypeClaim("x.*", "owner", "state")
    validate_fact_type_claims((c,))
    validate_fact_type_claims((c, c, FactTypeClaim("x.a*", "owner", "state")))


@pytest.mark.parametrize("claims", [[], (object(),), (None,)])
def test_staging_snapshot_requires_concrete_claims(claims):
    with pytest.raises(TypeError):
        validate_fact_type_claims(claims)


def test_conflict_is_detected_beyond_first_pair():
    claims = (
        FactTypeClaim("z", "z", "event"),
        FactTypeClaim("x.*", "a", "state"),
        FactTypeClaim("x.y", "b", "state"),
    )
    with pytest.raises(ValueError):
        validate_fact_type_claims(claims)


def test_no_recursion_or_recursive_wildcards():
    word = "a" * 1500
    assert fact_type_matches(word + "*", word)
    assert not fact_type_patterns_overlap(word, word + "b")


# Independent oracle: enumerate short concrete words and match by expanding stars.
# For <=3-token patterns over{a,b,*}, any common witness has length <=6:
# concatenating all literals is an upper bound; star-only witnesses need length1.
def finite_language(pattern):
    words = ("".join(chars) for n in range(1, 7) for chars in product("ab", repeat=n))

    @lru_cache(None)
    def accepts(pattern, word):
        if not pattern:
            return not word
        if pattern[0] == "*":
            return any(accepts(pattern[1:], word[n:]) for n in range(len(word) + 1))
        return bool(word) and pattern[0] == word[0] and accepts(pattern[1:], word[1:])

    return {word for word in words if accepts(pattern, word)}


short_patterns = st.text(alphabet="ab*", min_size=1, max_size=3)


@given(short_patterns, short_patterns)
def test_overlap_agrees_with_independent_finite_language(left, right):
    expected = bool(finite_language(left) & finite_language(right))
    assert fact_type_patterns_overlap(left, right) is expected


@given(st.lists(st.text(alphabet="ab😀", min_size=1, max_size=6), min_size=1, max_size=4))
def test_concrete_witness_implies_overlap(segments):
    concrete = ".".join(segments)
    prefix = ".".join(part[0] + "*" for part in segments)
    suffix = ".".join("*" + part[-1] for part in segments)
    assert fact_type_matches(prefix, concrete)
    assert fact_type_matches(suffix, concrete)
    assert fact_type_patterns_overlap(prefix, suffix)
    assert fact_type_patterns_overlap(suffix, prefix)


@given(st.lists(short_patterns, min_size=1, max_size=5))
def test_pattern_self_overlap_and_equivalent_owner_composition(segments):
    pattern = ".".join(segments)
    assert fact_type_patterns_overlap(pattern, pattern)
    validate_fact_type_claims((FactTypeClaim(pattern, "owner", "event"),) * 2)


def test_equivalent_pair_does_not_skip_later_conflicts():
    owner = FactTypeClaim("x.*", "owner", "state")
    equivalent = FactTypeClaim("x.a*", "owner", "state")
    conflict = FactTypeClaim("x.ab", "other", "state")
    with pytest.raises(ValueError):
        validate_fact_type_claims((owner, equivalent, conflict))


@pytest.mark.parametrize("left,right", [("*a", "*b"), ("a*", "b*"), ("a*b", "a*c"), ("a", "b")])
def test_wildcard_search_stays_within_finite_product(left, right, monkeypatch):
    # Monitor the finite automaton's state domain and enqueue bound, rather than
    # introducing a machine-speed timeout or a product pattern-length limit.
    bound = 1 + 3 * (len(left) + 1) * (len(right) + 1)

    class BoundedQueue(deque):
        def __init__(self, items):
            super().__init__(items)
            self.enqueued = len(self)

        def append(self, state):
            i, j = state
            assert 0 <= i <= len(left)
            assert 0 <= j <= len(right)
            self.enqueued += 1
            assert self.enqueued <= bound
            super().append(state)

    monkeypatch.setattr(fact_types, "deque", BoundedQueue)
    assert not fact_type_patterns_overlap(left, right)
