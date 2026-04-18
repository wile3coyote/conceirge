import pytest


@pytest.mark.asyncio
async def test_update_settings_persists_auto_grab_false(async_client):
    response = await async_client.put("/settings", json={"auto_grab": False})

    assert response.status_code == 200
    assert response.json()["auto_grab"] is False

    get_response = await async_client.get("/settings")

    assert get_response.status_code == 200
    assert get_response.json()["auto_grab"] is False
