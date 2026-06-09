"""Tests for whatsapp_phone_id unique constraint handling."""


def test_update_whatsapp_duplicate_raises_business_error(client, admin_token, mock_db):
    chain = mock_db.client.table.return_value
    chain.update.return_value = chain
    chain.eq.return_value = chain
    chain.execute.side_effect = Exception(
        'duplicate key value violates unique constraint "idx_organizations_whatsapp_phone_id_unique"'
    )

    from tests.conftest import ORG_A

    response = client.patch(
        f"/api/v1/organizations/{ORG_A}/whatsapp",
        json={"whatsapp_phone_id": "999888777"},
        cookies={"session_token": admin_token},
        headers={"x-organization-id": "ALL"},
    )

    assert response.status_code == 422
    assert "whatsapp_phone_id" in response.json()["detail"]
