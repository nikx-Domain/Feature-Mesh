import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def get_auth_token():
    # Helper to bypass or authenticate
    # Depending on how the auth is set up, we might need a real JWT. 
    # For e2e tests, we assume a test token or a mocked auth dependency.
    # To keep it simple in this test, we assume we have a way to inject or bypass.
    pass

@pytest.mark.skip(reason="Requires a valid JWT token and DB connection to run fully end-to-end")
def test_full_platform_lifecycle():
    headers = {"Authorization": "Bearer TEST_TOKEN"}
    
    # 1. Create Organization
    org_res = client.post("/api/v1/organizations", json={"name": "Acme Corp"}, headers=headers)
    assert org_res.status_code == 201
    org_id = org_res.json()["id"]
    
    # 2. Create Project
    proj_res = client.post(f"/api/v1/organizations/{org_id}/projects", json={"name": "Frontend App", "description": ""}, headers=headers)
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["id"]
    
    # 3. Create Environment
    env_res = client.post(f"/api/v1/projects/{proj_id}/environments", json={"name": "Production", "color": "red"}, headers=headers)
    assert env_res.status_code == 201
    env_id = env_res.json()["id"]
    
    # 4. Create Flag
    flag_res = client.post(f"/api/v1/projects/{proj_id}/flags", json={"name": "New Checkout", "key": "new_checkout", "type": "boolean"}, headers=headers)
    assert flag_res.status_code == 201
    
    # 5. Evaluate Flag
    eval_res = client.post(f"/api/v1/evaluation", json={"flag_key": "new_checkout", "context": {"user_id": "123"}}, headers={"X-Environment-Id": env_id})
    assert eval_res.status_code == 200
    assert "variation_value" in eval_res.json()
