from __future__ import annotations

from custom_components.heima.reconciliation import reconcile_ha_backed_options


def test_reconcile_imports_new_ha_persons_and_rooms():
    updated, summary, changed = reconcile_ha_backed_options(
        {},
        ha_people=[{"entity_id": "person.alex", "display_name": "Alex"}],
        ha_areas=[{"area_id": "living", "display_name": "Living"}],
    )

    assert changed is True
    assert updated["people_named"][0]["person_entity"] == "person.alex"
    assert updated["people_named"][0]["ha_sync_status"] == "new"
    assert updated["rooms"][0]["area_id"] == "living"
    assert updated["rooms"][0]["ha_sync_status"] == "new"
    assert summary["people"]["new_labels"] == ["Alex"]
    assert summary["rooms"]["new_labels"] == ["Living"]


def test_reconcile_marks_missing_person_and_room_as_orphaned():
    updated, summary, changed = reconcile_ha_backed_options(
        {
            "people_named": [
                {
                    "slug": "alex",
                    "display_name": "Alex",
                    "presence_method": "ha_person",
                    "person_entity": "person.alex",
                    "heima_reviewed": True,
                }
            ],
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "heima_reviewed": True,
                }
            ],
        },
        ha_people=[],
        ha_areas=[],
    )

    assert changed is True
    assert updated["people_named"][0]["ha_sync_status"] == "orphaned"
    assert updated["rooms"][0]["ha_sync_status"] == "orphaned"
    assert summary["people"]["orphaned_labels"] == ["alex"]
    assert summary["rooms"]["orphaned_labels"] == ["Living"]


def test_reconcile_preserves_reviewed_objects_as_configured():
    updated, summary, changed = reconcile_ha_backed_options(
        {
            "people_named": [
                {
                    "slug": "alex",
                    "display_name": "Alex",
                    "presence_method": "ha_person",
                    "person_entity": "person.alex",
                    "heima_reviewed": True,
                    "ha_source_name": "Alex",
                }
            ],
            "rooms": [
                {
                    "room_id": "living",
                    "display_name": "Living",
                    "area_id": "living",
                    "heima_reviewed": True,
                    "ha_source_name": "Living",
                }
            ],
        },
        ha_people=[{"entity_id": "person.alex", "display_name": "Alex"}],
        ha_areas=[{"area_id": "living", "display_name": "Living"}],
    )

    assert changed is True
    assert updated["people_named"][0]["ha_sync_status"] == "configured"
    assert updated["rooms"][0]["ha_sync_status"] == "configured"
    assert summary["people"]["configured_total"] == 1
    assert summary["rooms"]["configured_total"] == 1


def test_reconcile_rooms_auto_links_missing_area_id_by_room_id_match():
    updated, summary, changed = reconcile_ha_backed_options(
        {
            "rooms": [
                {
                    "room_id": "studio",
                    "display_name": "Studio",
                    "occupancy_sources": [],
                    "learning_sources": [],
                    "heima_reviewed": False,
                }
            ]
        },
        ha_people=[],
        ha_areas=[{"area_id": "studio", "display_name": "Studio"}],
    )

    assert changed is True
    room = updated["rooms"][0]
    assert room["area_id"] == "studio"
    assert room["ha_sync_status"] == "new"
    assert summary["rooms"]["orphaned_total"] == 0


def test_reconcile_people_auto_links_missing_person_entity_by_slug_match():
    updated, summary, changed = reconcile_ha_backed_options(
        {
            "people_named": [
                {
                    "slug": "alex",
                    "display_name": "Alex",
                    "presence_method": "ha_person",
                    "heima_reviewed": False,
                }
            ]
        },
        ha_people=[{"entity_id": "person.alex", "display_name": "Alex"}],
        ha_areas=[],
    )

    assert changed is True
    person = updated["people_named"][0]
    assert person["person_entity"] == "person.alex"
    assert person["ha_sync_status"] == "new"
    assert summary["people"]["orphaned_total"] == 0


def test_reconcile_people_deduplicates_legacy_and_auto_import_placeholder():
    updated, summary, changed = reconcile_ha_backed_options(
        {
            "people_named": [
                {
                    "slug": "stefano",
                    "display_name": "",
                    "presence_method": "ha_person",
                    "person_entity": "",
                    "heima_reviewed": True,
                },
                {
                    "slug": "stefano_2",
                    "display_name": "Stefano",
                    "presence_method": "ha_person",
                    "person_entity": "person.stefano",
                    "ha_sync_status": "new",
                    "heima_reviewed": False,
                },
            ]
        },
        ha_people=[{"entity_id": "person.stefano", "display_name": "Stefano"}],
        ha_areas=[],
    )

    assert changed is True
    assert [person["slug"] for person in updated["people_named"]] == ["stefano"]
    assert updated["people_named"][0]["person_entity"] == "person.stefano"
    assert updated["people_named"][0]["display_name"] == "Stefano"
    assert summary["people"]["total"] == 1
