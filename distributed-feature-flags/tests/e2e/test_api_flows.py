import pytest
from httpx import AsyncClient
import uuid
import asyncio

# Assuming we use httpx AsyncClient for proper async fixture support in FastAPI tests
# with the real database engine configured for the test environment.

@pytest.mark.asyncio
async def test_full_platform_lifecycle():
    # Because we're spinning up the real app, we use httpx to simulate real HTTP requests
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Generate a unique test email
        unique_id = str(uuid.uuid4())
        email = f"e2e_user_{unique_id}@acme.com"
        password = "SecurePassword123!"
        
        # 1. Register User
        res = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
        assert res.status_code == 201, res.text
        
        # 2. Login
        res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        token = res.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Create Organization
        org_res = await client.post("/api/v1/organizations", json={"name": "Acme Corp"}, headers=headers)
        assert org_res.status_code == 201, org_res.text
        org_id = org_res.json()["id"]
        
        # 4. Create Project
        proj_res = await client.post(f"/api/v1/organizations/{org_id}/projects", json={"name": "Frontend App", "description": ""}, headers=headers)
        assert proj_res.status_code == 201, proj_res.text
        proj_id = proj_res.json()["id"]
        
        # 5. Create Environment
        env_res = await client.post(f"/api/v1/projects/{proj_id}/environments", json={"name": "Production", "color": "red"}, headers=headers)
        assert env_res.status_code == 201, env_res.text
        env_id = env_res.json()["id"]
        
        # 6. Create Feature Flag
        flag_res = await client.post(f"/api/v1/projects/{proj_id}/flags", json={"name": "New Checkout", "key": f"new_checkout_{unique_id}", "type": "boolean"}, headers=headers)
        assert flag_res.status_code == 201, flag_res.text
        flag_id = flag_res.json()["id"]
        
        # We need the variations created automatically to reference them
        variations = flag_res.json()["variations"]
        var_true = next(v for v in variations if v["value"] is True)
        var_false = next(v for v in variations if v["value"] is False)
        
        # Enable Flag in Environment
        env_state_res = await client.post(f"/api/v1/flags/{flag_id}/environments/{env_id}/toggle", json={"is_enabled": True}, headers=headers)
        # Note: assuming the toggle endpoint exists based on earlier phases. If not, update logic.
        # Wait, typically we update the environment state or rules.
        
        # 7. Add Targeting Rule
        rule_res = await client.post(f"/api/v1/flags/{flag_id}/environments/{env_id}/rules/targeting", json={
            "attribute": "country",
            "operator": "equals",
            "value": "US",
            "serve_variation_id": var_true["id"],
            "priority": 0
        }, headers=headers)
        assert rule_res.status_code == 201, rule_res.text
        
        # 8. Evaluate Flag (Targets Rule -> US)
        eval_res = await client.post(f"/api/v1/evaluation", json={
            "flag_key": f"new_checkout_{unique_id}",
            "context": {"user_id": "123", "country": "US"}
        }, headers={"X-Environment-Id": env_id, "Authorization": f"Bearer {token}"})
        assert eval_res.status_code == 200, eval_res.text
        assert eval_res.json()["variation_value"] is True
        
        # 9. Evaluate Flag (Fallback -> Default)
        eval_res2 = await client.post(f"/api/v1/evaluation", json={
            "flag_key": f"new_checkout_{unique_id}",
            "context": {"user_id": "124", "country": "CA"}
        }, headers={"X-Environment-Id": env_id, "Authorization": f"Bearer {token}"})
        assert eval_res2.status_code == 200, eval_res2.text
        
        # 10. Audit Logs Retrieval
        # Wait a small moment to ensure eventual consistency if audits are async
        await asyncio.sleep(0.5)
        audit_res = await client.get(f"/api/v1/organizations/{org_id}/audit-logs", headers=headers)
        assert audit_res.status_code == 200, audit_res.text
        logs = audit_res.json()["items"]
        assert len(logs) > 0
        assert any(log["action"] == "flag.created" for log in logs)
