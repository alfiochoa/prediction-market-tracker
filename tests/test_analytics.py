from datetime import datetime, timezone

from pmtracker.alerts import MockWebhook, build_payload
from pmtracker.analytics import digest_markdown, filter_markets, fmt_pp, movers, top_markets
from pmtracker.charts import arrow, sparkline
from pmtracker.models import Market, Snapshot


def mk(i, p, p24, p7, cat="A", vol=10):
    return Market(id=str(i), question=f"Will thing {i} happen?", url="https://m/x", category=cat, probability=p,
                  p_24h=p24, p_7d=p7, volume_24h=vol, history=[(0, p7), (1, p)] if p7 is not None else [])


SNAP = Snapshot(generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc), markets=[
    mk(1, .8, .5, .4, "A", 30), mk(2, .3, .35, .6, "B", 20), mk(3, .5, None, None, "A", 10)])


def test_top_and_sort():
    assert [m.id for m in top_markets(SNAP.markets, 2)] == ["1", "2"]


def test_movers_sorted_by_abs_and_skips_unknown():
    assert [m.id for m in movers(SNAP.markets, "24h")] == ["1", "2"]
    assert [m.id for m in movers(SNAP.markets, "7d")] == ["1", "2"]
    assert [m.id for m in movers(SNAP.markets, "7d", min_abs=0.35)] == ["1"]


def test_filter_category_and_query():
    assert [m.id for m in filter_markets(SNAP, "A")] == ["1", "3"]
    assert [m.id for m in filter_markets(SNAP, None, "THING 2")] == ["2"]
    assert filter_markets(SNAP, None, "zzz") == []


def test_fmt_pp_never_negative_zero():
    assert fmt_pp(-0.0004) == "0.0 pp" and fmt_pp(0.123) == "+12.3 pp" and fmt_pp(None) == "n/a"


def test_digest_has_disclaimer_attribution_and_groups():
    md = digest_markdown(SNAP)
    assert "not investment advice" in md and "Manifold Markets" in md
    assert "Biggest risers" in md and "Biggest fallers" in md and "Will thing 1" in md


def test_alert_payload_and_mock_outbox(tmp_path):
    p = build_payload(SNAP, 0.10, "24h")
    assert [m["change_pp"] for m in p["movers"]] == [30.0]
    box = tmp_path / "o.jsonl"
    MockWebhook(box).send(p)
    assert box.read_text().count("\n") == 1


def test_sparkline_and_arrow():
    assert "<polyline" in sparkline(SNAP.markets[0]) and "<polyline" not in sparkline(Market(id="x", question="q", url="u", probability=.5))
    assert arrow(0.2) == "▲" and arrow(-0.2) == "▼" and arrow(0.001) == "•"
