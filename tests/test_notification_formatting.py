from __future__ import annotations

from custom_components.heima.coordinator import (
    _house_state_proposal_notification_message,
    _installer_notification_message,
)


def test_house_state_notification_uses_weekday_name_and_formatted_hour() -> None:
    message = _house_state_proposal_notification_message(
        proposal_id="proposal-1",
        context_snapshot={
            "predicted_state": "guest",
            "weekday": 5,
            "hour_bucket": 8,
            "rooms": ["bagno_piccolo"],
            "anyone_home": True,
        },
        confidence=1.0,
    )

    assert "Context: Saturday, 08:00" in message
    assert "weekday 5" not in message
    assert "hour 8" not in message


def test_installer_anomaly_notification_formats_temporal_context() -> None:
    message = _installer_notification_message(
        {
            "severity": "warning",
            "key": "anomaly.alarm_disarm_unusual_hour",
            "message": "Alarm was disarmed at an unusual hour.",
            "context": {
                "anomaly_type": "alarm_disarm_unusual_hour",
                "weekday": 5,
                "current_hour_bucket": 2,
                "baseline_hour_bucket": 7.5,
            },
        }
    )

    assert "Weekday: Saturday" in message
    assert "Observed hour: 02:00" in message
    assert "Historical median hour: 07:30" in message
