"""The shared RFC-8785 encoding boundary; domain limits belong to payloads."""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Protocol, cast

import rfc8785

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | dict[str, JsonValue] | list[JsonValue]


class _DataclassParameters(Protocol):
    frozen: bool


def canonical_json_bytes(value: object) -> bytes:
    """Encode a JSON projection, including frozen collections/record fields.

    No text parser is provided here: duplicate keys must be rejected by the future
    decoding boundary before they can be lost in a Python dictionary.
    """
    try:
        return rfc8785.dumps(_project(value, set()))
    except (rfc8785.CanonicalizationError, UnicodeError) as error:
        raise ValueError("Payload has no valid RFC-8785 representation") from error


def _project(value: object, ancestors: set[int]) -> JsonValue:
    if isinstance(value, Enum):
        raise ValueError("Enum objects are not JSON values")
    if type(value) in (str, int, float, bool) or value is None:
        return cast(JsonScalar, value)
    identity = id(value)
    if identity in ancestors:
        raise ValueError("Cyclic collections are not JSON values")
    ancestors.add(identity)
    try:
        if isinstance(value, (dict, MappingProxyType)):
            mapping: Mapping[object, object] = value
            if any(type(key) is not str for key in mapping):
                raise ValueError("JSON object keys must be strings")
            return {cast(str, key): _project(item, ancestors) for key, item in mapping.items()}
        if type(value) in (list, tuple):
            return [
                _project(item, ancestors) for item in cast(list[object] | tuple[object, ...], value)
            ]
        if is_dataclass(value) and not isinstance(value, type):
            if not cast(_DataclassParameters, getattr(type(value), "__dataclass_params__")).frozen:
                raise ValueError("Record must be a frozen dataclass")
            return {
                field.name: _project(getattr(value, field.name), ancestors)
                for field in fields(value)
            }
        raise ValueError("Unsupported JSON value type")
    finally:
        ancestors.remove(identity)
