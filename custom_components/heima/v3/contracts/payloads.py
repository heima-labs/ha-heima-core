"""Layer-1 payload construction: bounded validation and deep immutability."""

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum, StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Protocol, cast

from .canonical_json import canonical_json_bytes


class _DataclassParameters(Protocol):
    frozen: bool


MAX_SAFE_INTEGER = 2**53 - 1
MAX_COLLECTION_DEPTH = 2
MAX_PAYLOAD_BYTES = 8 * 1024


class PayloadErrorCode(StrEnum):
    TYPE = "invalid_type"
    INTEGER = "integer_out_of_range"
    NONFINITE = "nonfinite_number"
    UNICODE = "invalid_unicode"
    DEPTH = "collection_too_deep"
    SIZE = "payload_too_large"
    MAPPING = "mapping_required"


class PayloadValidationError(ValueError):
    """A bounded diagnosis that never retains an offending payload."""

    def __init__(self, code: PayloadErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True, eq=False)
class PreparedPayload:
    """Local construction result, not an additional persisted envelope.

    Instances are returned by the preparation functions. Canonical content, not
    Python's bool/int comparison or dict hashability, defines equality and hash.
    """

    value: object
    canonical_bytes: bytes

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PreparedPayload):
            return NotImplemented
        return self.canonical_bytes == other.canonical_bytes

    def __hash__(self) -> int:
        return hash(self.canonical_bytes)


@dataclass(frozen=True, slots=True)
class PayloadDiagnostic:
    code: PayloadErrorCode


@dataclass(frozen=True, slots=True)
class EvidencePreparation:
    payload: PreparedPayload
    diagnostics: tuple[PayloadDiagnostic, ...]


def freeze_house_fact_value(value: object) -> PreparedPayload:
    """Validate a value and return a detached, deeply frozen representation."""
    frozen = _freeze(value, 0, record_context=False, allow_record=True)
    encoded = canonical_json_bytes(frozen)
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise PayloadValidationError(PayloadErrorCode.SIZE)
    return PreparedPayload(frozen, encoded)


def validate_house_fact_value(value: object) -> None:
    """The staging validator required by Layer 1 §3; shares construction rules."""
    freeze_house_fact_value(value)


def freeze_persisted_projection(value: object) -> PreparedPayload:
    """Prepare a mapping projection without the fact-value dataclass exception."""
    if type(value) is not dict:
        raise PayloadValidationError(PayloadErrorCode.MAPPING)
    return freeze_house_fact_value(value)


def prepare_evidence(value: object) -> EvidencePreparation:
    """Discard invalid supporting evidence and return one bounded diagnostic."""
    try:
        return EvidencePreparation(freeze_persisted_projection(value), ())
    except PayloadValidationError as error:
        empty = freeze_persisted_projection({})
        return EvidencePreparation(empty, (PayloadDiagnostic(error.code),))


def _freeze(value: object, depth: int, *, record_context: bool, allow_record: bool) -> object:
    value_type = type(value)
    if isinstance(value, Enum):
        raise PayloadValidationError(PayloadErrorCode.TYPE)
    if value is None or value_type is bool:
        return value
    if value_type is str:
        try:
            cast(str, value).encode("utf-8")
        except UnicodeError as error:
            raise PayloadValidationError(PayloadErrorCode.UNICODE) from error
        return value
    if value_type is int:
        if not -MAX_SAFE_INTEGER <= cast(int, value) <= MAX_SAFE_INTEGER:
            raise PayloadValidationError(PayloadErrorCode.INTEGER)
        return value
    if value_type is float:
        if not isfinite(cast(float, value)):
            raise PayloadValidationError(PayloadErrorCode.NONFINITE)
        return value
    if value_type is dict:
        _check_depth(depth)
        copied = {}
        for key, item in cast(dict[object, object], value).items():
            if type(key) is not str:
                raise PayloadValidationError(PayloadErrorCode.TYPE)
            frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=False)
            copied[frozen_key] = _freeze(
                item, depth + 1, record_context=record_context, allow_record=record_context
            )
        return MappingProxyType(copied)
    if value_type is list or (value_type is tuple and record_context):
        _check_depth(depth)
        return tuple(
            _freeze(item, depth + 1, record_context=record_context, allow_record=record_context)
            for item in cast(list[object] | tuple[object, ...], value)
        )
    if allow_record and is_dataclass(value) and not isinstance(value, type):
        if not cast(_DataclassParameters, getattr(value_type, "__dataclass_params__")).frozen:
            raise PayloadValidationError(PayloadErrorCode.TYPE)
        _check_depth(depth)
        # Copy only declared data fields. Do not rerun arbitrary __init__/post-init
        # callbacks, and never copy an instance's undeclared mutable attributes.
        copied_record = object.__new__(value_type)
        for field in fields(value):
            item = _freeze(
                getattr(value, field.name), depth + 1, record_context=True, allow_record=True
            )
            object.__setattr__(copied_record, field.name, item)
        return copied_record
    raise PayloadValidationError(PayloadErrorCode.TYPE)


def _check_depth(depth: int) -> None:
    if depth >= MAX_COLLECTION_DEPTH:
        raise PayloadValidationError(PayloadErrorCode.DEPTH)
