import pytest
from httpx import AsyncClient
import uuid
import asyncio

# Assuming we use httpx AsyncClient for proper async fixture support in FastAPI tests
# with the real database engine configured for the test environment.

@pytest.mark.asyncio
async def test_full_platform_lifecycle():
    # Because we're spinning up the real app, we use httpx to simulate real HTTP requests
    from app.main import app, lifespan
    from httpx import ASGITransport
    
    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
            org_res = await client.post("/api/v1/tenancy/organizations", json={"name": "Acme Corp"}, headers=headers)
            assert org_res.status_code == 201, org_res.text
            org_id = org_res.json()["id"]
            headers["X-Tenant-ID"] = org_id
            
            # 4. Create Project
            proj_res = await client.post("/api/v1/tenancy/projects", json={"name": "Frontend App", "description": ""}, headers=headers)
            assert proj_res.status_code == 201, proj_res.text
            proj_id = proj_res.json()["id"]
            
            # 5. Create Environment
            env_res = await client.post(f"/api/v1/tenancy/projects/{proj_id}/environments", json={"name": "Production"}, headers=headers)
            assert env_res.status_code == 201, env_res.text
            env_id = env_res.json()["id"]
            
            # 6. Create Feature Flag
            flag_key = f"new_checkout_{unique_id}"
            flag_res = await client.post(f"/api/v1/projects/{proj_id}/flags", json={"name": "New Checkout", "key": flag_key, "type": "boolean"}, headers=headers)
            assert flag_res.status_code == 201, flag_res.text
            flag_id = flag_res.json()["id"]
            
            # 7. Enable Flag in Environment
            env_state_res = await client.patch(f"/api/v1/environments/{env_id}/flags/{flag_id}/toggle", json={"is_enabled": True}, headers=headers)
            assert env_state_res.status_code == 200, env_state_res.text
            
            # 8. Evaluate Flag
            eval_res = await client.post(f"/api/v1/environments/{env_id}/evaluate/{flag_key}", json={
                "context": {"key": "123", "attributes": {"country": "US"}}
            }, headers=headers)
            assert eval_res.status_code == 200, eval_res.text
            assert eval_res.json()["variation_value"] is False
            
            # 9. Audit Logs Retrieval
            # Manually process outbox events since Kafka is not running locally
            from app.infrastructure.db.models import OutboxEvent
            from sqlalchemy import select
            from app.core.database import SessionLocal
            from app.main import audit_consumer
            from unittest.mock import MagicMock
            import json
            
            async with SessionLocal() as session:
                result = await session.execute(select(OutboxEvent))
                events = result.scalars().all()
                for event in events:
                    msg = MagicMock()
                    # Parse payload to get the actual event_id
                    if isinstance(event.payload, str):
                        payload_dict = json.loads(event.payload)
                        payload_bytes = event.payload.encode("utf-8")
                    else:
                        payload_dict = event.payload
                        payload_bytes = json.dumps(payload_dict).encode("utf-8")
                        
                    event_id = payload_dict.get("event_id", str(uuid.uuid4()))
                    
                    msg.headers = [
                        ("event_type", event.event_type.encode("utf-8")),
                        ("event_id", event_id.encode("utf-8"))
                    ]
                    msg.value = payload_bytes
                    await audit_consumer.process_message(msg)
                    
            await asyncio.sleep(0.5)
            audit_res = await client.get("/api/v1/audit-events", headers=headers)
            assert audit_res.status_code == 200, audit_res.text
            logs = audit_res.json()
            assert len(logs) > 0
            assert any(log["action"] == "created" for log in logs)
