"""Unit tests for Phase AW1: House State Learning Completion Visualization — proposal_id join + 7x24 matrix."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# Helper to simulate the frontend join logic in pure Python for unit testing
def _house_state_accepted_proposals_by_context_key_py(proposals_raw):
    """Python equivalent of _houseStateAcceptedProposalsByContextKey for unit testing."""
    accepted_by_context_key = {}
    prefix = "house_state_learned_context:"
    for proposal in proposals_raw:
        if proposal.get("status") != "accepted":
            continue
        identity_key = proposal.get("identity_key") or ""
        if not identity_key.startswith(prefix):
            continue
        context_key = identity_key[len(prefix):]
        if context_key:
            accepted_by_context_key[context_key] = proposal.get("id")
    return accepted_by_context_key


def _group_house_state_entries_by_slot_py(entries):
    """Python equivalent of _groupHouseStateEntriesBySlot for unit testing."""
    slots = {}
    for entry in entries:
        snapshot = entry.get("context_snapshot") or {}
        weekday = snapshot.get("weekday")
        hour_bucket = snapshot.get("hour_bucket")
        if weekday is None or hour_bucket is None:
            continue
        slot_key = f"{weekday},{hour_bucket}"
        if slot_key not in slots:
            slots[slot_key] = {"weekday": weekday, "hour_bucket": hour_bucket, "entries": []}
        slots[slot_key]["entries"].append(entry)
    return slots


class TestHouseStateAcceptedProposalsByContextKey:
    """Tests for _houseStateAcceptedProposalsByContextKey helper (AW1 join logic)."""

    def test_returns_empty_map_for_empty_proposals(self):
        result = _house_state_accepted_proposals_by_context_key_py([])
        assert result == {}

    def test_returns_empty_map_for_no_accepted_proposals(self):
        proposals = [
            {"id": "p1", "status": "pending", "identity_key": "house_state_learned_context:key1"},
            {"id": "p2", "status": "rejected", "identity_key": "house_state_learned_context:key2"},
        ]
        result = _house_state_accepted_proposals_by_context_key_py(proposals)
        assert result == {}

    def test_returns_map_for_accepted_house_state_proposals(self):
        proposals = [
            {"id": "p1", "status": "accepted", "identity_key": "house_state_learned_context:weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working"},
            {"id": "p2", "status": "accepted", "identity_key": "house_state_learned_context:weekday:2:hour_bucket:10:rooms:kitchen:anyone_home:0:ctx:def:state:away"},
            {"id": "p3", "status": "pending", "identity_key": "house_state_learned_context:weekday:3:hour_bucket:12:rooms:bedroom:anyone_home:1:ctx:ghi:state:sleeping"},
        ]
        result = _house_state_accepted_proposals_by_context_key_py(proposals)
        
        assert len(result) == 2
        assert "weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working" in result
        assert result["weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working"] == "p1"
        assert "weekday:2:hour_bucket:10:rooms:kitchen:anyone_home:0:ctx:def:state:away" in result
        assert result["weekday:2:hour_bucket:10:rooms:kitchen:anyone_home:0:ctx:def:state:away"] == "p2"

    def test_filters_non_house_state_proposals(self):
        proposals = [
            {"id": "p1", "status": "accepted", "identity_key": "activity_discovered:activity:cook"},
            {"id": "p2", "status": "accepted", "identity_key": "house_state_learned_context:weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working"},
        ]
        result = _house_state_accepted_proposals_by_context_key_py(proposals)
        
        assert len(result) == 1
        assert "weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working" in result

    def test_handles_missing_identity_key(self):
        proposals = [
            {"id": "p1", "status": "accepted"},  # no identity_key
            {"id": "p2", "status": "accepted", "identity_key": ""},  # empty identity_key
        ]
        result = _house_state_accepted_proposals_by_context_key_py(proposals)
        assert result == {}

    def test_handles_prefix_without_context_key(self):
        proposals = [
            {"id": "p1", "status": "accepted", "identity_key": "house_state_learned_context:"},  # empty after prefix
            {"id": "p2", "status": "accepted", "identity_key": "house_state_learned_context"},  # no colon
        ]
        result = _house_state_accepted_proposals_by_context_key_py(proposals)
        assert result == {}


class TestGroupHouseStateEntriesBySlot:
    """Tests for _groupHouseStateEntriesBySlot helper (AW1 grouping logic)."""

    def test_returns_empty_dict_for_empty_entries(self):
        result = _group_house_state_entries_by_slot_py([])
        assert result == {}

    def test_groups_single_entry(self):
        entries = [
            {
                "context_snapshot": {"weekday": 1, "hour_bucket": 8},
                "predicted_state": "working",
            }
        ]
        result = _group_house_state_entries_by_slot_py(entries)
        
        assert len(result) == 1
        assert "1,8" in result
        assert result["1,8"]["weekday"] == 1
        assert result["1,8"]["hour_bucket"] == 8
        assert len(result["1,8"]["entries"]) == 1

    def test_groups_multiple_entries_same_slot(self):
        entries = [
            {
                "context_snapshot": {"weekday": 1, "hour_bucket": 8},
                "predicted_state": "working",
            },
            {
                "context_snapshot": {"weekday": 1, "hour_bucket": 8},
                "predicted_state": "relax",
            },
        ]
        result = _group_house_state_entries_by_slot_py(entries)
        
        assert len(result) == 1
        assert "1,8" in result
        assert len(result["1,8"]["entries"]) == 2

    def test_groups_multiple_entries_different_slots(self):
        entries = [
            {"context_snapshot": {"weekday": 1, "hour_bucket": 8}, "predicted_state": "working"},
            {"context_snapshot": {"weekday": 1, "hour_bucket": 9}, "predicted_state": "relax"},
            {"context_snapshot": {"weekday": 2, "hour_bucket": 8}, "predicted_state": "sleeping"},
        ]
        result = _group_house_state_entries_by_slot_py(entries)
        
        assert len(result) == 3
        assert "1,8" in result
        assert "1,9" in result
        assert "2,8" in result

    def test_skips_entries_with_missing_weekday(self):
        entries = [
            {"context_snapshot": {"hour_bucket": 8}, "predicted_state": "working"},
            {"context_snapshot": {"weekday": 1, "hour_bucket": 8}, "predicted_state": "working"},
        ]
        result = _group_house_state_entries_by_slot_py(entries)
        
        assert len(result) == 1
        assert "1,8" in result

    def test_skips_entries_with_missing_hour_bucket(self):
        entries = [
            {"context_snapshot": {"weekday": 1}, "predicted_state": "working"},
            {"context_snapshot": {"weekday": 1, "hour_bucket": 8}, "predicted_state": "working"},
        ]
        result = _group_house_state_entries_by_slot_py(entries)
        
        assert len(result) == 1
        assert "1,8" in result

    def test_skips_entries_with_missing_context_snapshot(self):
        entries = [
            {"predicted_state": "working"},  # no context_snapshot
            {"context_snapshot": {"weekday": 1, "hour_bucket": 8}, "predicted_state": "working"},
        ]
        result = _group_house_state_entries_by_slot_py(entries)
        
        assert len(result) == 1
        assert "1,8" in result


class TestJoinAndGroupingIntegration:
    """Integration tests for the complete AW1 join + grouping flow."""

    def test_full_flow_single_slot_single_proposal(self):
        proposals_raw = [
            {
                "id": "prop_123",
                "status": "accepted",
                "identity_key": "house_state_learned_context:weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working"
            }
        ]
        entries = [
            {
                "context_key": "weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working",
                "context_snapshot": {"weekday": 1, "hour_bucket": 8, "rooms": ["living"], "anyone_home": True},
                "predicted_state": "working",
                "count": 22,
                "total": 25,
                "confidence": 0.88,
            }
        ]
        
        # Step 1: Build context_key -> proposal_id map
        accepted_by_context_key = _house_state_accepted_proposals_by_context_key_py(proposals_raw)
        
        # Step 2: Join proposal_id onto entries
        entries_with_id = []
        for entry in entries:
            entries_with_id.append({
                **entry,
                "proposal_id": accepted_by_context_key.get(entry["context_key"]) or None,
            })
        
        # Step 3: Group by slot
        slots = _group_house_state_entries_by_slot_py(entries_with_id)
        
        # Verify
        assert len(slots) == 1
        assert "1,8" in slots
        assert len(slots["1,8"]["entries"]) == 1
        assert slots["1,8"]["entries"][0]["proposal_id"] == "prop_123"

    def test_full_flow_multiple_slots_multiple_proposals(self):
        proposals_raw = [
            {
                "id": "prop_001",
                "status": "accepted",
                "identity_key": "house_state_learned_context:weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working"
            },
            {
                "id": "prop_002",
                "status": "accepted",
                "identity_key": "house_state_learned_context:weekday:1:hour_bucket:8:rooms:kitchen:anyone_home:0:ctx:def:state:away"
            },
            {
                "id": "prop_003",
                "status": "accepted",
                "identity_key": "house_state_learned_context:weekday:2:hour_bucket:10:rooms:living:anyone_home:1:ctx:ghi:state:relax"
            },
        ]
        entries = [
            {
                "context_key": "weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working",
                "context_snapshot": {"weekday": 1, "hour_bucket": 8},
                "predicted_state": "working",
            },
            {
                "context_key": "weekday:1:hour_bucket:8:rooms:kitchen:anyone_home:0:ctx:def:state:away",
                "context_snapshot": {"weekday": 1, "hour_bucket": 8},
                "predicted_state": "away",
            },
            {
                "context_key": "weekday:2:hour_bucket:10:rooms:living:anyone_home:1:ctx:ghi:state:relax",
                "context_snapshot": {"weekday": 2, "hour_bucket": 10},
                "predicted_state": "relax",
            },
        ]
        
        accepted_by_context_key = _house_state_accepted_proposals_by_context_key_py(proposals_raw)
        entries_with_id = [{
            **entry,
            "proposal_id": accepted_by_context_key.get(entry["context_key"]) or None,
        } for entry in entries]
        slots = _group_house_state_entries_by_slot_py(entries_with_id)
        
        # Verify: 2 slots (1,8 has 2 proposals, 2,10 has 1)
        assert len(slots) == 2
        assert "1,8" in slots
        assert "2,10" in slots
        
        # Slot 1,8 has 2 entries
        assert len(slots["1,8"]["entries"]) == 2
        
        # Slot 2,10 has 1 entry
        assert len(slots["2,10"]["entries"]) == 1

    def test_join_miss_returns_null_proposal_id(self):
        """When context_key has no matching proposal, proposal_id should be null."""
        proposals_raw = [
            {
                "id": "prop_001",
                "status": "accepted",
                "identity_key": "house_state_learned_context:weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working"
            }
        ]
        entries = [
            {
                "context_key": "weekday:1:hour_bucket:8:rooms:living:anyone_home:1:ctx:abc:state:working",
                "context_snapshot": {"weekday": 1, "hour_bucket": 8},
                "predicted_state": "working",
            },
            {
                "context_key": "weekday:2:hour_bucket:10:rooms:kitchen:anyone_home:0:ctx:def:state:away",
                "context_snapshot": {"weekday": 2, "hour_bucket": 10},
                "predicted_state": "away",
            },
        ]
        
        accepted_by_context_key = _house_state_accepted_proposals_by_context_key_py(proposals_raw)
        entries_with_id = [{
            **entry,
            "proposal_id": accepted_by_context_key.get(entry["context_key"]) or None,
        } for entry in entries]
        
        # First entry has matching proposal
        assert entries_with_id[0]["proposal_id"] == "prop_001"
        # Second entry has no matching proposal
        assert entries_with_id[1]["proposal_id"] is None
