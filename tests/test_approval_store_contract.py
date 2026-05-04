from __future__ import annotations

from custom_components.heima.runtime.inference.approval_store import (
    ApprovalRecord,
    ApprovalStore,
)


def test_approval_record_requires_approved_by_role() -> None:
    record = ApprovalRecord(
        proposal_id="proposal-1",
        proposal_type="house_state_learned_context",
        decision="approved",
        approved_by="installer",
    )

    assert record.approved_by == "installer"
    assert record.as_dict()["approved_by"] == "installer"


def test_approval_record_from_dict_rejects_missing_approved_by() -> None:
    assert (
        ApprovalRecord.from_dict(
            {
                "proposal_id": "proposal-1",
                "proposal_type": "house_state_learned_context",
                "decision": "approved",
            }
        )
        is None
    )


def test_approval_record_from_dict_accepts_resident_and_installer_roles() -> None:
    resident = ApprovalRecord.from_dict(
        {
            "proposal_id": "proposal-1",
            "proposal_type": "house_state_learned_context",
            "decision": "approved",
            "approved_by": "resident",
        }
    )
    installer = ApprovalRecord.from_dict(
        {
            "proposal_id": "proposal-2",
            "proposal_type": "activity_discovered",
            "decision": "rejected",
            "approved_by": "installer",
            "metadata": {"source": "service"},
        }
    )

    assert resident is not None
    assert resident.approved_by == "resident"
    assert installer is not None
    assert installer.approved_by == "installer"
    assert installer.metadata == {"source": "service"}


def test_approval_store_contract_reserves_storage_key() -> None:
    assert ApprovalStore.STORAGE_KEY == "heima_inference_approvals"
