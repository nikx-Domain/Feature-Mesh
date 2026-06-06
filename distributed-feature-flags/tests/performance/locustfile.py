from locust import HttpUser, task, between, events
import random
import uuid

# Usage: 
# locust -f tests/performance/locustfile.py --headless -u 1000 -r 100 --run-time 1m --host=http://localhost:8000

class FeatureFlagUser(HttpUser):
    # Wait between 0.01s and 0.1s between tasks to simulate intense load
    wait_time = between(0.01, 0.1)

    def on_start(self):
        """
        Setup required before tasks run.
        We simulate different users by giving them unique IDs.
        """
        self.user_id = str(uuid.uuid4())
        self.headers = {
            "Authorization": "Bearer TEST_TOKEN", # Assumes load testing environment bypasses auth or uses static token
            "X-Environment-Id": "test-env-id"
        }

    @task(3)
    def evaluate_flag_hit(self):
        """
        Simulates standard feature flag evaluation hits which represents 75% of traffic.
        """
        payload = {
            "flag_key": "new_checkout",
            "context": {
                "user_id": self.user_id,
                "country": random.choice(["US", "CA", "IN", "UK"]),
                "plan": random.choice(["free", "premium"])
            }
        }
        
        with self.client.post("/api/v1/evaluation", json=payload, headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with {response.status_code}")

    @task(1)
    def evaluate_flag_miss(self):
        """
        Simulates non-existent feature flag requests which represents 25% of traffic.
        This forces the backend to query DB and return 404.
        """
        payload = {
            "flag_key": f"missing_flag_{random.randint(1, 1000)}",
            "context": {
                "user_id": self.user_id
            }
        }
        
        # 404 is the expected behavior here, so we mark it as success if it returns 404
        with self.client.post("/api/v1/evaluation", json=payload, headers=self.headers, catch_response=True) as response:
            if response.status_code == 404:
                response.success()
            elif response.status_code == 200:
                response.failure("Expected 404 for missing flag, got 200")
            else:
                response.failure(f"Failed with {response.status_code}")
