"""CLI: `python -m pmtracker.cli snapshot` refreshes data/snapshot.json + digest + mock alerts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .alerts import MockWebhook, build_payload
from .analytics import digest_markdown
from .log import event, get_logger
from .providers import DEFAULT_SNAPSHOT, ManifoldProvider

log = get_logger("pmtracker.cli")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pmtracker")
    ap.add_argument("command", choices=["snapshot"])
    ap.add_argument("--out", type=Path, default=DEFAULT_SNAPSHOT)
    ap.add_argument("--threshold", type=float, default=0.10)
    args = ap.parse_args(argv)
    try:
        snap = ManifoldProvider().fetch_snapshot()
    except Exception as e:  # keep the committed snapshot on failure
        event(log, "refresh_failed", 40, error=str(e))
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(snap.model_dump_json(indent=None))
    (args.out.parent / "digest.md").write_text(digest_markdown(snap))
    MockWebhook(args.out.parent / "alerts_outbox.jsonl").send(build_payload(snap, args.threshold))
    event(log, "refresh_ok", markets=len(snap.markets), path=str(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
