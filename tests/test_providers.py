import httpx
import pytest

from pmtracker.http import ApiClient
from pmtracker.models import Snapshot
from pmtracker.providers import DEFAULT_SNAPSHOT, FixtureProvider, ManifoldProvider, downsample


@pytest.fixture
def snap(api_handler):
    c = ApiClient("https://api.test/v0", transport=httpx.MockTransport(api_handler), sleep=lambda s: None, min_interval=0)
    return ManifoldProvider(c).fetch_snapshot()


def test_filters_invalid_and_non_binary(snap):
    ids = {m.id for m in snap.markets}
    assert ids == {"m1", "m2"}  # invalid row skipped, MULTIPLE_CHOICE dropped


def test_changes_from_bet_history(snap):
    m = next(x for x in snap.markets if x.id == "m1")
    assert m.category == "Politics" and m.p_24h == pytest.approx(0.4) and m.p_7d == pytest.approx(0.3)
    assert m.change_24h == pytest.approx(0.3)
    assert len(m.history) >= 3 and m.history[-1][1] == 0.7


def test_no_bets_means_flat(snap):
    m = next(x for x in snap.markets if x.id == "m2")
    assert m.change_24h == 0 and m.history == []


def test_ranked_by_24h_volume(snap):
    assert [m.id for m in snap.markets] == ["m1", "m2"]


def test_downsample_bounds():
    pts = [(i, i / 1000) for i in range(1000)]
    assert len(downsample(pts, 0, 1000, 48)) <= 48


def test_bundled_snapshot_is_valid_and_nonempty():
    s = FixtureProvider(DEFAULT_SNAPSHOT).fetch_snapshot()
    assert isinstance(s, Snapshot) and len(s.markets) >= 10 and s.generated_at.tzinfo
    assert all(0 <= m.probability <= 1 for m in s.markets)
