"""Sparkline SVG (single series, 2px line, end marker, no axes) and detail chart helpers."""
from __future__ import annotations

import html
from typing import Optional

from .models import Market

UP, DOWN, FLAT = "#16a34a", "#dc2626", "#64748b"  # status hues; always paired with an arrow glyph + sign


def trend_color(delta: Optional[float]) -> str:
    if delta is None or abs(delta) < 0.005:
        return FLAT
    return UP if delta > 0 else DOWN


def arrow(delta: Optional[float]) -> str:
    if delta is None or abs(delta) < 0.005:
        return "•"
    return "▲" if delta > 0 else "▼"


def sparkline(m: Market, w: int = 120, h: int = 34) -> str:
    pts = m.history
    if len(pts) < 2:
        return f'<svg width="{w}" height="{h}" role="img" aria-label="no history"></svg>'
    t0, t1 = pts[0][0], pts[-1][0]
    span = max(t1 - t0, 1)
    pad = 4
    xy = [(pad + (t - t0) / span * (w - 2 * pad), pad + (1 - p) * (h - 2 * pad)) for t, p in pts]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    ex, ey = xy[-1]
    label = html.escape(f"7-day probability: {pts[0][1]:.0%} to {pts[-1][1]:.0%}")
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{label}">'
            f'<title>{label}</title>'
            f'<polyline points="{path}" fill="none" stroke="currentColor" stroke-opacity=".55" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="{trend_color(m.change_7d)}" stroke="var(--background-color, #fff)" stroke-width="2"/></svg>')
