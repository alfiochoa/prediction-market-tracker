import time

import httpx
import pytest

NOW = int(time.time() * 1000)
H = 3_600_000


def market(i, prob=0.5, vol24=100, **kw):
    d = {"id": f"m{i}", "question": f"Question {i}?", "url": f"https://manifold.markets/u/q{i}", "probability": prob,
         "outcomeType": "BINARY", "volume": 1000, "volume24Hours": vol24, "totalLiquidity": 500,
         "closeTime": NOW + 90 * 24 * H, "uniqueBettorCount": 7, "isResolved": False}
    d.update(kw)
    return d


@pytest.fixture
def api_handler():
    """Fake Manifold: two search results (one invalid), bets with a known 24h/7d history."""
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.url.path.endswith("/search-markets"):
            if req.url.params.get("topicSlug") == "politics-default":
                return httpx.Response(200, json=[market(1, 0.7, 500), market(2, 0.2, 300), {"id": "bad", "probability": 9}])
            return httpx.Response(200, json=[market(3, 0.4, 50, outcomeType="MULTIPLE_CHOICE")])
        if req.url.path.endswith("/bets"):
            cid = req.url.params["contractId"]
            if cid == "m1":
                return httpx.Response(200, json=[
                    {"id": "b2", "createdTime": NOW - 3 * H, "probBefore": 0.4, "probAfter": 0.7},
                    {"id": "b1", "createdTime": NOW - 3 * 24 * H, "probBefore": 0.3, "probAfter": 0.4}])
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    handler.calls = calls
    return handler
