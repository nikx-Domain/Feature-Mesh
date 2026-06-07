import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_rate_limiting_login(client: AsyncClient):
    # Hit the limit
    for _ in range(5):
        response = await client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "wrong"})
        assert response.status_code in (401, 403, 429)

    # The 6th request should be rate limited
    response = await client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "wrong"})
    assert response.status_code == 429

async def test_refresh_token_replay(client: AsyncClient, user, db_session):
    # Attempt to login to get a refresh token
    response = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "password"})
    assert response.status_code == 200
    data = response.json()
    refresh_token = data["refresh_token"]

    # First refresh should succeed
    refresh_resp1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp1.status_code == 200

    # Second refresh with the SAME token should fail (replay attack)
    refresh_resp2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp2.status_code == 401
    assert "Token reuse detected" in refresh_resp2.json()["detail"]
