"""Shared proposal-review rendering helpers for lighting entity steps."""

from __future__ import annotations

from typing import Any


def render_entity_steps_discovery_details(
    proposed_steps: list[dict[str, Any]],
    *,
    language: str,
    count_label_it: str = "Luci proposte",
    count_label_en: str = "Proposed lights",
) -> list[str]:
    """Render discovery review details for one proposed entity-step list."""
    is_it = language.startswith("it")
    entities = _entity_ids(proposed_steps)
    if not entities:
        return []

    details = [
        (
            f"Entità proposte: {', '.join(entities)}"
            if is_it
            else f"Proposed entities: {', '.join(entities)}"
        )
    ]
    details.append(
        f"{count_label_it}: {len(entities)}" if is_it else f"{count_label_en}: {len(entities)}"
    )
    return details


def render_entity_steps_tuning_details(
    current_steps: list[dict[str, Any]],
    proposed_steps: list[dict[str, Any]],
    *,
    language: str,
    count_label_it: str = "Luci",
    count_label_en: str = "Lights",
    header_it: str = "Delta luci:",
    header_en: str = "Delta lighting:",
) -> list[str]:
    """Render structured tuning diffs for lighting entity steps."""
    is_it = language.startswith("it")
    current_by_entity = _by_entity_id(current_steps)
    proposed_by_entity = _by_entity_id(proposed_steps)
    current_entities = sorted(current_by_entity)
    proposed_entities = sorted(proposed_by_entity)

    details: list[str] = []
    if current_entities or proposed_entities:
        details.append(
            f"Entità attuali: {', '.join(current_entities) if current_entities else '-'}"
            if is_it
            else f"Current entities: {', '.join(current_entities) if current_entities else '-'}"
        )
        details.append(
            f"Entità proposte: {', '.join(proposed_entities) if proposed_entities else '-'}"
            if is_it
            else f"Proposed entities: {', '.join(proposed_entities) if proposed_entities else '-'}"
        )

    diff_lines: list[str] = []
    if len(current_entities) != len(proposed_entities):
        diff_lines.append(
            f"{count_label_it}: {len(current_entities)} -> {len(proposed_entities)}"
            if is_it
            else f"{count_label_en}: {len(current_entities)} -> {len(proposed_entities)}"
        )

    added = sorted(set(proposed_entities) - set(current_entities))
    removed = sorted(set(current_entities) - set(proposed_entities))
    if added:
        diff_lines.append(
            f"Entità aggiunte: {', '.join(added)}"
            if is_it
            else f"Added entities: {', '.join(added)}"
        )
    if removed:
        diff_lines.append(
            f"Entità rimosse: {', '.join(removed)}"
            if is_it
            else f"Removed entities: {', '.join(removed)}"
        )

    for entity_id in sorted(set(current_entities) & set(proposed_entities)):
        field_diffs = _entity_field_diffs(
            current_by_entity[entity_id],
            proposed_by_entity[entity_id],
            is_it=is_it,
        )
        if field_diffs:
            diff_lines.append(f"{entity_id}: {'; '.join(field_diffs)}")

    if diff_lines:
        details.append(header_it if is_it else header_en)
        details.extend(diff_lines)
    return details


def _entity_ids(steps: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(step.get("entity_id") or "").strip()
            for step in steps
            if str(step.get("entity_id") or "").strip()
        }
    )


def _by_entity_id(steps: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(step.get("entity_id") or "").strip(): step
        for step in steps
        if str(step.get("entity_id") or "").strip()
    }


def _entity_field_diffs(
    current: dict[str, Any],
    proposed: dict[str, Any],
    *,
    is_it: bool,
) -> list[str]:
    field_diffs: list[str] = []

    current_action = str(current.get("action") or "").strip()
    proposed_action = str(proposed.get("action") or "").strip()
    if current_action != proposed_action:
        field_diffs.append(
            f"azione {current_action} -> {proposed_action}"
            if is_it
            else f"action {current_action} -> {proposed_action}"
        )

    current_brightness = current.get("brightness")
    proposed_brightness = proposed.get("brightness")
    if current_brightness != proposed_brightness:
        field_diffs.append(f"brightness {current_brightness} -> {proposed_brightness}")

    current_kelvin = current.get("color_temp_kelvin")
    proposed_kelvin = proposed.get("color_temp_kelvin")
    if current_kelvin != proposed_kelvin:
        field_diffs.append(f"color_temp_kelvin {current_kelvin} -> {proposed_kelvin}")

    current_rgb = current.get("rgb_color")
    proposed_rgb = proposed.get("rgb_color")
    if current_rgb != proposed_rgb:
        field_diffs.append(f"rgb_color {current_rgb} -> {proposed_rgb}")

    return field_diffs
