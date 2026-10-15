"""Fact-type grammar and claim conflicts, resolved only during staging."""

from collections import deque
from dataclasses import dataclass
from itertools import combinations
from typing import Literal

from .canonical_json import canonical_json_bytes

type FactEmissionKind = Literal["state", "event"]


def _segments(pattern: str) -> tuple[str, ...]:
    if type(pattern) is not str:
        raise TypeError("Fact identifiers require primitive strings")
    segments = tuple(pattern.split("."))
    if any(not segment for segment in segments):
        raise ValueError("Fact identifiers require nonempty dotted segments")
    canonical_json_bytes(pattern)
    return segments


def validate_fact_type(fact_type: str) -> None:
    """Validate one concrete identifier, never a wildcard claim."""
    _segments(fact_type)
    if "*" in fact_type:
        raise ValueError("Concrete fact identifiers cannot contain wildcards")


@dataclass(frozen=True, slots=True)
class FactTypeClaim:
    fact_type_pattern: str
    owner_id: str
    emission_kind: FactEmissionKind

    def __post_init__(self) -> None:
        _segments(self.fact_type_pattern)
        if type(self.owner_id) is not str:
            raise TypeError("Fact claim owner must be a primitive string")
        canonical_json_bytes(self.owner_id)
        if type(self.emission_kind) is not str:
            raise TypeError("Fact emission kind must be a primitive string")
        if self.emission_kind not in ("state", "event"):
            raise ValueError("Unknown fact emission kind")


def fact_type_matches(pattern: str, fact_type: str) -> bool:
    """Staging-only complete identifier matching; all non-star characters literal."""
    left = _segments(pattern)
    validate_fact_type(fact_type)
    return _patterns_overlap(left, tuple(fact_type.split(".")))


def fact_type_patterns_overlap(left: str, right: str) -> bool:
    """Whether there is a valid nonempty-segment concrete witness for both."""
    return _patterns_overlap(_segments(left), _segments(right))


def validate_fact_type_claims(claims: tuple[FactTypeClaim, ...]) -> None:
    """Check a staging snapshot; this alone does not admit or authorize producers.

    The future composition owner must include reserved core claims and validate
    exact state locations, then resolve kind/owner into producer-specific ports.
    """
    if type(claims) is not tuple:
        raise TypeError("Fact claim validation requires an immutable tuple")
    for claim in claims:
        if type(claim) is not FactTypeClaim:
            raise TypeError("Fact claim validation requires concrete claims")
        FactTypeClaim.__post_init__(claim)
    for left, right in combinations(claims, 2):
        if left.owner_id == right.owner_id and left.emission_kind == right.emission_kind:
            continue
        if fact_type_patterns_overlap(left.fact_type_pattern, right.fact_type_pattern):
            raise ValueError("Overlapping fact claims disagree on owner or emission kind")


def _patterns_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if len(left) != len(right):
        return False
    return all(_segments_overlap(a, b) for a, b in zip(left, right, strict=True))


def _segments_overlap(left: str, right: str) -> bool:
    # Product automaton: each '*' has an epsilon skip and a consuming self-loop.
    # A common empty witness requires two all-star segments; these also share
    # any one literal. Thus accepting the product always has a nonempty witness.
    pending = deque([(0, 0)])
    visited = set()
    while pending:
        i, j = pending.popleft()
        state = (i, j)
        if state in visited:
            continue
        visited.add(state)
        if i == len(left) and j == len(right):
            return True
        a = left[i] if i < len(left) else None
        b = right[j] if j < len(right) else None
        if a == "*":
            pending.append((i + 1, j))
        if b == "*":
            pending.append((i, j + 1))
        if a is None or b is None:
            continue
        if a == "*" or b == "*" or a == b:
            pending.append((i if a == "*" else i + 1, j if b == "*" else j + 1))
    return False
