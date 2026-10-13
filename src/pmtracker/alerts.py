"""Biggest-movers alerts. The webhook is MOCKED: payloads go to a local outbox file, nothing is sent."""
from __future__ import annotations

import json
from pathlib import Path

from . import DISCLAIMER
from .analytics import movers
from .log import event, get_logger
from .models import Snapshot

log = get_logger("pmtracker.alerts")


def build_payload(snap: Snapshot, threshold: float = 0.10, window: str = "24h") -> dict:
    hits = movers(snap.markets, window, n=10, min_abs=threshold)
    return {"type": "biggest_movers", "window": window, "threshold_pp": threshold * 100,
            "generated_at": snap.generated_at.isoformat(), "note": DISCLAIMER,
            "movers": [{"question": m.question, "url": m.url, "probability": round(m.probability, 4),
                        "change_pp": round((m.change_24h if window == "24h" else m.change_7d) * 100, 1)}
                       for m in hits]}


class MockWebhook:
    """Stands in for e.g. a Slack/Discord webhook; appends JSON lines to an outbox file."""

    def __init__(self, outbox: Path = Path("data/alerts_outbox.jsonl")):
        self.outbox = Path(outbox)

    def send(self, payload: dict) -> None:
        self.outbox.parent.mkdir(parents=True, exist_ok=True)
        with self.outbox.open("a") as f:
            f.write(json.dumps(payload) + "\n")
        event(log, "mock_webhook_sent", movers=len(payload["movers"]))
