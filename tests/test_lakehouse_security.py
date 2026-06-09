"""Lakehouse SQL endpoints — super_admin only."""


def test_lakehouse_query_org_admin_forbidden(client, user_token):
    res = client.post(
        "/api/v1/lakehouse/query",
        json={"query": "SELECT id FROM patients LIMIT 1"},
        cookies={"session_token": user_token},
        headers={"x-organization-id": "22222222-2222-2222-2222-222222222222"},
    )
    assert res.status_code == 403


def test_lakehouse_generate_sql_org_admin_forbidden(client, user_token):
    res = client.post(
        "/api/v1/lakehouse/generate-sql",
        json={"prompt": "listar pacientes"},
        cookies={"session_token": user_token},
        headers={"x-organization-id": "22222222-2222-2222-2222-222222222222"},
    )
    assert res.status_code == 403
