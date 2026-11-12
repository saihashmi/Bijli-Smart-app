from app.middleware.ratelimit import LIMITS, RateLimiter


def test_bucket_allows_burst_then_blocks_then_refills():
    rl = RateLimiter()
    cap = LIMITS["destructive"].capacity
    for _ in range(cap):
        assert rl.hit("destructive", "ws1", now=0.0) == 0
    wait = rl.hit("destructive", "ws1", now=0.0)
    assert wait > 0
    assert rl.hit("destructive", "ws2", now=0.0) == 0  # other workspaces unaffected
    assert rl.hit("destructive", "ws1", now=wait + 0.01) == 0  # refilled


def test_endpoint_returns_429_with_retry_after(client):
    client.get("/api/settings")
    codes = [client.delete("/api/workspace/data").status_code for _ in range(LIMITS["destructive"].capacity + 1)]
    assert codes[:-1] == [200] * LIMITS["destructive"].capacity
    assert codes[-1] == 429
    res = client.delete("/api/workspace/data")
    assert res.json()["error"]["code"] == "RATE_LIMITED"
    assert int(res.headers["retry-after"]) >= 1
