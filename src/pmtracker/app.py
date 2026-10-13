"""Streamlit dashboard. Reads the bundled snapshot (offline-safe); never shows a blank page."""
from __future__ import annotations

import html
from datetime import datetime, timezone

import altair as alt
import streamlit as st

from pmtracker import ATTRIBUTION, DISCLAIMER
from pmtracker.alerts import MockWebhook, build_payload
from pmtracker.analytics import SORTS, digest_markdown, filter_markets, fmt_pp, movers, top_markets
from pmtracker.charts import arrow, sparkline, trend_color
from pmtracker.models import Market
from pmtracker.providers import FixtureProvider

CSS = """
<style>
.block-container{max-width:1080px;padding-top:2.2rem}
.pm-note{font-size:13px;opacity:.8;border-left:3px solid #2563eb;padding:6px 12px;margin:4px 0 14px}
.pm-meta{font-size:12px;opacity:.65;margin-bottom:8px}
.pm-row{display:grid;grid-template-columns:1fr 78px 98px 124px 92px;gap:14px;align-items:center;
 padding:12px 4px;border-bottom:1px solid color-mix(in srgb,currentColor 14%,transparent)}
.pm-row.head{font-size:12px;opacity:.6;text-transform:uppercase;letter-spacing:.04em;padding:6px 4px}
.pm-q{font-size:15px;line-height:1.35}.pm-q a{color:inherit;text-decoration:none;font-weight:600}
.pm-q a:hover{text-decoration:underline}
.pm-sub{font-size:12px;opacity:.65;margin-top:2px}
.pm-prob{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
.pm-chg{font-size:14px;font-variant-numeric:tabular-nums;white-space:nowrap}
.pm-small{font-size:13px;opacity:.8}
.pm-lbl{display:none}
@media (max-width:760px){
 .pm-row{grid-template-columns:1fr 1fr;gap:6px 12px}.pm-row.head{display:none}
 .pm-q{grid-column:1/-1}.pm-lbl{display:block;font-size:11px;opacity:.55}}
</style>
"""


@st.cache_data(show_spinner=False)
def load_snapshot():
    return FixtureProvider().fetch_snapshot()


def rows_html(markets: list[Market]) -> str:
    head = ('<div class="pm-row head"><div>Market</div><div>Prob.</div><div>24h</div>'
            '<div>7-day trend</div><div>Closes</div></div>')
    out = [head]
    for m in markets:
        c = trend_color(m.change_24h)
        close = m.close_time.strftime("%b %d, %Y") if m.close_time else "n/a"
        out.append(
            f'<div class="pm-row"><div class="pm-q"><a href="{html.escape(m.url)}" target="_blank" rel="noopener">'
            f'{html.escape(m.question)}</a><div class="pm-sub">{html.escape(m.category)} · 24h vol {m.volume_24h:,.0f} MANA'
            f' · liquidity {m.liquidity:,.0f}</div></div>'
            f'<div><span class="pm-lbl">Probability</span><span class="pm-prob">{m.probability:.0%}</span></div>'
            f'<div class="pm-chg"><span class="pm-lbl">24h change</span><span style="color:{c}">{arrow(m.change_24h)}</span> {fmt_pp(m.change_24h)}</div>'
            f'<div><span class="pm-lbl">7-day trend</span>{sparkline(m)}<div class="pm-sub">7d {arrow(m.change_7d)} {fmt_pp(m.change_7d)}</div></div>'
            f'<div class="pm-small"><span class="pm-lbl">Closes</span>{close}</div></div>')
    return "".join(out)


def detail_chart(m: Market):
    import pandas as pd
    df = pd.DataFrame(m.history, columns=["t", "p"])
    df["time"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    base = alt.Chart(df).encode(x=alt.X("time:T", title=None), y=alt.Y("p:Q", title="Probability", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")))
    line = base.mark_line(strokeWidth=2, interpolate="step-after", color="#2563eb")
    pts = base.mark_point(size=60, filled=True, opacity=0, color="#2563eb").encode(
        tooltip=[alt.Tooltip("time:T", title="Time (UTC)", format="%b %d %H:%M"), alt.Tooltip("p:Q", title="Probability", format=".1%")])
    return (line + pts).properties(height=260).configure_axis(grid=True, gridOpacity=0.15, domain=False)


def main() -> None:
    st.set_page_config(page_title="Prediction Market Tracker", page_icon="📈", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    snap = load_snapshot()
    st.title("Prediction Market Tracker")
    st.markdown(f'<div class="pm-note"><b>Play-money prediction data, not forecasts or advice.</b> '
                f'Manifold Markets uses play money (MANA). Reference/demo data for illustration only. {ATTRIBUTION}</div>',
                unsafe_allow_html=True)
    age = snap.age_hours()
    st.markdown(f'<div class="pm-meta">Snapshot generated {snap.generated_at:%Y-%m-%d %H:%M UTC} '
                f'({age:.0f} h ago) · refreshed by a scheduled GitHub Action · {len(snap.markets)} binary markets</div>',
                unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 1, 1])
    query = c1.text_input("Search markets", placeholder="e.g. election, AI, rate", label_visibility="collapsed")
    cat = c2.selectbox("Category", ["All"] + snap.categories, label_visibility="collapsed")
    sort = c3.selectbox("Rank by", list(SORTS), label_visibility="collapsed")
    pool = filter_markets(snap, cat, query)

    tab_top, tab_mov, tab_dig, tab_about = st.tabs(["Top 10", "Biggest movers", "Weekly digest", "About"])
    with tab_top:
        top = top_markets(pool, 10, SORTS[sort])
        if not top:
            st.info("No markets match this search. Clear the filters to see the full snapshot.")
        else:
            st.markdown(rows_html(top), unsafe_allow_html=True)
            pick = st.selectbox("Probability history", [m.id for m in top], format_func=lambda i: next(m.question for m in top if m.id == i))
            m = next(x for x in top if x.id == pick)
            if len(m.history) > 1:
                st.altair_chart(detail_chart(m), use_container_width=True)
            with st.expander("Table view"):
                st.dataframe([{"Question": x.question, "Category": x.category, "Probability": round(x.probability, 3),
                               "24h change (pp)": None if x.change_24h is None else round(x.change_24h * 100, 1),
                               "7d change (pp)": None if x.change_7d is None else round(x.change_7d * 100, 1),
                               "24h volume": round(x.volume_24h), "Liquidity": round(x.liquidity),
                               "Closes": x.close_time.date().isoformat() if x.close_time else None} for x in top], hide_index=True)
    with tab_mov:
        a, b = st.columns(2)
        window = a.radio("Window", ["24h", "7d"], horizontal=True)
        thr = b.slider("Alert threshold (percentage points)", 1, 30, 10)
        mv = movers(pool, window, 8, thr / 100)
        if mv:
            st.markdown(rows_html(mv), unsafe_allow_html=True)
        else:
            st.info(f"No market moved by {thr} pp or more in {window} for this filter.")
        payload = build_payload(snap, thr / 100, window)
        with st.expander("Mock webhook payload (nothing is sent)"):
            st.json(payload)
    with tab_dig:
        md = digest_markdown(snap)
        st.markdown(md)
        st.download_button("Download digest.md", md, file_name="digest.md", mime="text/markdown")
    with tab_about:
        st.markdown(f"""
**What this is.** A dashboard over [Manifold Markets](https://manifold.markets)' public API: top active binary
markets, probability moves, history sparklines, a weekly digest and mocked mover alerts.

**What it is not.** {DISCLAIMER} There are no trading features. Probabilities reflect a play-money crowd, can be
thin or manipulated, and are not predictions you should act on.

**Data freshness.** This page reads a bundled snapshot (so it always loads, even offline) that a scheduled GitHub
Action refreshes. 24h/7d changes are computed from bet history at snapshot time.

{ATTRIBUTION}
""")


main()
