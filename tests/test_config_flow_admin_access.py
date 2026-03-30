from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.heima.config_flow import HeimaConfigFlow, HeimaOptionsFlowHandler


def _fake_hass(*, is_admin: bool) -> SimpleNamespace:
    async def _async_get_user(user_id: str):
        return SimpleNamespace(id=user_id, is_admin=is_admin)

    return SimpleNamespace(
        services=SimpleNamespace(async_services=lambda: {"notify": {}}),
        config=SimpleNamespace(time_zone="Europe/Rome", language="it"),
        data={},
        auth=SimpleNamespace(async_get_user=_async_get_user),
    )


@pytest.mark.asyncio
async def test_config_flow_user_step_requires_admin() -> None:
    flow = HeimaConfigFlow()
    flow.hass = _fake_hass(is_admin=False)
    flow.context = {"user_id": "user-1"}

    result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "admin_required"


@pytest.mark.asyncio
async def test_config_flow_user_step_allows_admin() -> None:
    flow = HeimaConfigFlow()
    flow.hass = _fake_hass(is_admin=True)
    flow.context = {"user_id": "user-1"}

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_options_flow_init_allows_admin() -> None:
    flow = HeimaOptionsFlowHandler(SimpleNamespace(options={}, entry_id="entry-1"))
    flow.hass = _fake_hass(is_admin=True)
    flow.context = {"user_id": "user-1"}

    result = await flow.async_step_init()

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
