import httpx
import pytest

from pmtracker import USER_AGENT
from pmtracker.http import ApiClient, ApiError


def client(handler, **kw):
    return ApiClient("https://x.test/v0", transport=httpx.MockTransport(handler), sleep=lambda s: None, min_interval=0, **kw)


def test_retries_then_succeeds():
    n = {"c": 0}

    def h(req):
        n["c"] += 1
        return httpx.Response(503) if n["c"] < 3 else httpx.Response(200, json={"ok": 1})

    assert client(h).get_json("a") == {"ok": 1} and n["c"] == 3


def test_gives_up_after_retries():
    with pytest.raises(ApiError, match="gave up"):
        client(lambda r: httpx.Response(429), retries=2).get_json("a")


def test_client_error_not_retried():
    n = {"c": 0}

    def h(req):
        n["c"] += 1
        return httpx.Response(404)

    with pytest.raises(ApiError, match="404"):
        client(h).get_json("a")
    assert n["c"] == 1


def test_user_agent_and_cache(tmp_path):
    seen = []

    def h(req):
        seen.append(req.headers["user-agent"])
        return httpx.Response(200, json=[1])

    c = client(h, cache_dir=tmp_path)
    assert c.get_json("a", {"q": 1}) == [1] and c.get_json("a", {"q": 1}) == [1]
    assert seen == [USER_AGENT]  # second call served from cache
