"""Pure functions over a Snapshot: ranking, movers, search/filter, markdown digest."""
from __future__ import annotations

from typing import Optional

from . import ATTRIBUTION, DISCLAIMER
from .models import Market, Snapshot

SORTS = {"24h volume": "volume_24h", "Liquidity": "liquidity", "Total volume": "volume"}


def filter_markets(snap: Snapshot, category: Optional[str] = None, query: str = "") -> list[Market]:
    q = query.strip().lower()
    return [m for m in snap.markets
            if (not category or category == "All" or m.category == category)
            and (not q or all(w in m.question.lower() for w in q.split()))]


def top_markets(markets: list[Market], n: int = 10, by: str = "volume_24h") -> list[Market]:
    return sorted(markets, key=lambda m: getattr(m, by), reverse=True)[:n]


def movers(markets: list[Market], window: str = "24h", n: int = 5, min_abs: float = 0.0) -> list[Market]:
    attr = "change_24h" if window == "24h" else "change_7d"
    cand = [m for m in markets if getattr(m, attr) is not None and abs(getattr(m, attr)) >= min_abs]
    return sorted(cand, key=lambda m: abs(getattr(m, attr)), reverse=True)[:n]


def fmt_pp(delta: Optional[float]) -> str:
    if delta is None:
        return "n/a"
    v = round(delta * 100, 1)
    return "0.0 pp" if v == 0 else f"{v:+.1f} pp"


def digest_markdown(snap: Snapshot, n: int = 5) -> str:
    ts = snap.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# What moved this week", "", f"_Snapshot generated {ts}._", "", f"> {DISCLAIMER}", ""]
    up = [m for m in movers(snap.markets, "7d", 50) if m.change_7d > 0][:n]
    down = [m for m in movers(snap.markets, "7d", 50) if m.change_7d < 0][:n]
    for title, group in (("Biggest risers (7 days)", up), ("Biggest fallers (7 days)", down)):
        lines += [f"## {title}", ""]
        if not group:
            lines += ["_No qualifying moves._", ""]
            continue
        lines += ["| Market | Now | 7d change | 24h volume (MANA) |", "|---|---|---|---|"]
        for m in group:
            lines.append(f"| [{m.question}]({m.url}) | {m.probability:.0%} | {fmt_pp(m.change_7d)} | {m.volume_24h:,.0f} |")
        lines.append("")
    lines += ["---", ATTRIBUTION, ""]
    return "\n".join(lines)
