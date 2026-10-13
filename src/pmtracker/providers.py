"""Provider/adapter layer: Manifold (live) and Fixture (bundled snapshot, offline)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol

from pydantic import ValidationError

from .http import ApiClient, ApiError
from .log import event, get_logger
from .models import Market, RawMarket, Snapshot

log = get_logger("pmtracker.providers")
BASE = "https://api.manifold.markets/v0"
DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "snapshot.json"
DAY_MS = 86_400_000
TOPICS = {"Politics": "politics-default", "Technology": "technology-default",
          "Economics": "economics-default", "Science": "science-default",
          "Sports": "sports-default", "World": "world-default", "Culture": "culture-default"}


class Provider(Protocol):
    def fetch_snapshot(self) -> Snapshot: ...


class FixtureProvider:
    """Loads a bundled snapshot; never touches the network."""

    def __init__(self, path: Path = DEFAULT_SNAPSHOT):
        self.path = Path(path)

    def fetch_snapshot(self) -> Snapshot:
        return Snapshot.model_validate_json(self.path.read_text())


def downsample(points: list[tuple[int, float]], start: int, end: int, n: int = 48) -> list[tuple[int, float]]:
    """Last value per time bucket across [start, end]; keeps the series small."""
    if len(points) <= n:
        return [(t, round(p, 4)) for t, p in points]
    width = (end - start) / n
    buckets: dict[int, tuple[int, float]] = {}
    for t, p in sorted(points):
        buckets[min(int((t - start) / width), n - 1)] = (t, round(p, 4))
    return [buckets[k] for k in sorted(buckets)]


def prob_at(bets: list[dict], t: int, current: float) -> float:
    """Probability at time t from a bet list (sorted ascending); None-safe fallback."""
    if not bets:
        return current
    before = [b for b in bets if b["createdTime"] <= t]
    return before[-1]["probAfter"] if before else bets[0]["probBefore"]


class ManifoldProvider:
    def __init__(self, client: Optional[ApiClient] = None, per_topic: int = 8, top_n: int = 36):
        self.client = client or ApiClient(BASE, cache_dir=Path(".cache"))
        self.per_topic, self.top_n = per_topic, top_n

    def _search(self, topic: Optional[str], limit: int) -> list[dict]:
        params = {"term": "", "sort": "24-hour-vol", "filter": "open", "contractType": "BINARY", "limit": limit}
        if topic:
            params["topicSlug"] = topic
        return self.client.get_json("search-markets", params)

    def _bets(self, market_id: str, after: int, pages: int = 3) -> list[dict]:
        out: list[dict] = []
        before = None
        for _ in range(pages):
            params = {"contractId": market_id, "afterTime": after, "limit": 1000}
            if before:
                params["before"] = before
            page = self.client.get_json("bets", params)
            out += page
            if len(page) < 1000:
                break
            before = page[-1]["id"]
        return sorted(out, key=lambda b: b["createdTime"])

    def fetch_snapshot(self) -> Snapshot:
        now_ms = int(time.time() * 1000)
        seen: dict[str, tuple[RawMarket, str]] = {}
        sources = [(c, s, self.per_topic) for c, s in TOPICS.items()] + [("General", None, 15)]
        for cat, slug, lim in sources:
            try:
                items = self._search(slug, lim)
            except ApiError as e:
                event(log, "topic_failed", 40, topic=cat, error=str(e))
                continue
            for it in items:
                try:
                    raw = RawMarket.model_validate(it)
                except ValidationError as e:
                    event(log, "invalid_market_skipped", 30, id=it.get("id"), error=str(e)[:120])
                    continue
                if raw.outcomeType != "BINARY" or raw.isResolved or (raw.closeTime and raw.closeTime < now_ms):
                    continue
                seen.setdefault(raw.id, (raw, cat))
        if not seen:
            raise ApiError("no markets fetched")
        ranked = sorted(seen.values(), key=lambda rc: rc[0].volume24Hours, reverse=True)[: self.top_n]
        markets = []
        for raw, cat in ranked:
            try:
                bets = self._bets(raw.id, now_ms - 7 * DAY_MS)
            except ApiError as e:
                event(log, "history_failed", 30, id=raw.id, error=str(e))
                bets = []
            hist = [(b["createdTime"], b["probAfter"]) for b in bets]
            hist = [(max(now_ms - 7 * DAY_MS, bets[0]["createdTime"] - 1), bets[0]["probBefore"])] + hist if bets else []
            if hist:
                hist.append((now_ms, raw.probability))
            markets.append(Market(
                id=raw.id, question=raw.question, url=raw.url, category=cat, probability=raw.probability,
                volume=raw.volume, volume_24h=raw.volume24Hours, liquidity=raw.totalLiquidity,
                bettors=raw.uniqueBettorCount,
                close_time=datetime.fromtimestamp(raw.closeTime / 1000, timezone.utc) if raw.closeTime else None,
                p_24h=prob_at(bets, now_ms - DAY_MS, raw.probability),
                p_7d=prob_at(bets, now_ms - 7 * DAY_MS, raw.probability),
                history=downsample(hist, now_ms - 7 * DAY_MS, now_ms)))
        event(log, "snapshot_built", markets=len(markets))
        return Snapshot(generated_at=datetime.now(timezone.utc), markets=markets)
