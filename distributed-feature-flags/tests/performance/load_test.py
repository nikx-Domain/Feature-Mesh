import asyncio
import time
import httpx
from statistics import quantiles, mean

async def load_test_evaluation(base_url: str, api_key: str, requests_per_sec: int, duration_sec: int):
    """
    Executes a high-concurrency load test against the /evaluate API.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    total_requests = requests_per_sec * duration_sec
    latencies = []
    errors = 0
    
    # We will use an AsyncClient to flood the API
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10.0) as client:
        
        async def fetch():
            nonlocal errors
            start = time.perf_counter()
            try:
                # Assuming 'test_flag' exists in the environment
                response = await client.post("/api/v1/evaluation", json={
                    "flag_key": "test_flag",
                    "context": {"user_id": "load_tester", "country": "US"}
                })
                if response.status_code != 200:
                    errors += 1
            except Exception:
                errors += 1
            latencies.append(time.perf_counter() - start)

        print(f"Starting load test: {requests_per_sec} req/s for {duration_sec}s (Total: {total_requests})")
        
        # Batching requests to hit the target requests_per_sec
        for sec in range(duration_sec):
            start_sec = time.perf_counter()
            tasks = [fetch() for _ in range(requests_per_sec)]
            await asyncio.gather(*tasks)
            elapsed = time.perf_counter() - start_sec
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)

    # Calculate P50, P95, P99
    latencies.sort()
    if not latencies:
        print("No requests completed.")
        return
        
    p50 = latencies[int(len(latencies) * 0.50)] * 1000
    p95 = latencies[int(len(latencies) * 0.95)] * 1000
    p99 = latencies[int(len(latencies) * 0.99)] * 1000
    avg = mean(latencies) * 1000
    
    print("\n--- Load Test Results ---")
    print(f"Total Requests: {len(latencies)}")
    print(f"Error Rate: {(errors / len(latencies)) * 100:.2f}%")
    print(f"Avg Latency: {avg:.2f} ms")
    print(f"P50 Latency: {p50:.2f} ms")
    print(f"P95 Latency: {p95:.2f} ms")
    print(f"P99 Latency: {p99:.2f} ms")

if __name__ == "__main__":
    # Example usage:
    # asyncio.run(load_test_evaluation("http://localhost:8000", "test_api_key", requests_per_sec=100, duration_sec=5))
    pass
