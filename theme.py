"""Colours, Plotly styling, CSS and HTML components for the Coach View.

Purple and white theme on a grey canvas with white cards, packed to fit one
1440x900 screen with no page scroll. The categorical pair (Freo purple,
opposition orange) was validated for lightness, chroma, colour-vision
separation and contrast on a light surface. Colour follows the entity (Freo is
always purple), never rank. No club logo or trademarks.
"""

import html

import streamlit as st

COLORS = {
    "freo": "#7C3AED",     # Fremantle (categorical slot 1)
    "opp": "#C25E12",      # Opposition (categorical slot 2)
    "win": "#15803D",
    "loss": "#DC2626",
    "ink": "#1F2937",
    "muted": "#6B7280",
    "grid": "#E7E3EF",
    "brand": "#2A0A4A",    # deep Freo purple (header band)
    "spark": "#B8A6DC",    # sparkline de-emphasis hue
}

FONT = "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"


def style_fig(fig, y_title="", unified=True, height=240):
    """Shared chart look: transparent surface, recessive grid and axes, a compact
    legend across the top, a single y axis (never dual-axis)."""
    fig.update_layout(
        template="plotly_white",
        font=dict(family=FONT, color=COLORS["ink"], size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=4, r=6, t=24, b=4),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                    font=dict(color=COLORS["muted"], size=11)),
        hovermode="x unified" if unified else "closest",
        height=height,
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(color=COLORS["muted"]),
                     linecolor=COLORS["grid"])
    fig.update_yaxes(title=dict(text=y_title, font=dict(color=COLORS["muted"], size=11)),
                     gridcolor=COLORS["grid"], zeroline=False,
                     tickfont=dict(color=COLORS["muted"]))
    return fig


def inject_css():
    st.markdown(
        """
        <style>
          /* One screen: no Streamlit chrome, tight padding and gaps. */
          header[data-testid="stHeader"], footer, #MainMenu,
          [data-testid="stToolbar"], [data-testid="stDecoration"],
          section[data-testid="stSidebar"], [data-testid="collapsedControl"] { display:none !important; }
          .block-container { padding:8px 14px 0 !important; max-width:100% !important; }
          div[data-testid="stVerticalBlock"] { gap:6px; }
          div[data-testid="stHorizontalBlock"] { gap:8px; }
          div[data-testid="stElementContainer"]:has(> .stPlotlyChart) { margin:0; }

          /* Cards: keyed containers (st-key-card_*), plus the older wrapper name */
          div[class*="st-key-card_"],
          div[data-testid="stVerticalBlockBorderWrapper"] {
            background:#FFFFFF; border:1px solid #E7E3EF !important; border-radius:10px;
            box-shadow:0 1px 2px rgba(42,10,74,.06);
          }
          div[class*="st-key-card_"] { gap:2px; }
          div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] { gap:2px; }
          .st-key-deep_dive [data-baseweb="select"] * { font-size:.8rem; }
          .card-title {
            text-transform:uppercase; letter-spacing:.07em; font-size:.66rem;
            font-weight:700; color:#6D28D9; margin:0; line-height:1.6;
          }
          .card-title span { color:#9CA3AF; font-weight:600; text-transform:none; letter-spacing:0; }
          .card-title .key { color:#4B5563; margin-left:10px; white-space:nowrap; }
          .card-title .key i { display:inline-block; width:9px; height:9px; border-radius:2px;
            margin-right:4px; vertical-align:-1px; }

          /* Header band */
          .cv-band {
            background:linear-gradient(100deg,#2A0A4A 0%,#4C1D95 60%,#6D28D9 100%);
            color:#fff; border-radius:10px; padding:7px 14px; height:52px;
            display:flex; align-items:center; gap:clamp(10px, 1.2vw, 22px); overflow:hidden;
          }
          .cv-band .ttl { font-weight:700; font-size:1.05rem; white-space:nowrap; }
          .cv-band .ttl small { display:block; font-weight:500; font-size:.66rem; color:#C4B5FD; }
          .cv-stat { line-height:1.05; white-space:nowrap; }
          .cv-stat b { font-size:1.08rem; font-weight:700; }
          .cv-stat span { display:block; font-size:.62rem; letter-spacing:.08em;
            text-transform:uppercase; color:#C4B5FD; }
          .cv-form { display:flex; gap:3px; }
          .cv-form i { font-style:normal; font-size:.66rem; font-weight:700; width:20px;
            height:20px; border-radius:4px; display:flex; align-items:center;
            justify-content:center; color:#fff; }

          /* Headline tiles */
          .cv-tiles { margin:2px 0 8px; display:grid; grid-template-columns:repeat(8,1fr); gap:8px; }
          .cv-tile { background:#fff; border:1px solid #E7E3EF; border-radius:10px;
            padding:6px 8px 4px; min-width:0; box-shadow:0 1px 2px rgba(42,10,74,.06); }
          .cv-tile .lbl { font-size:.66rem; color:#6B7280; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .cv-tile .val { font-size:1.15rem; font-weight:650; color:#2A0A4A; line-height:1.15; }
          .cv-tile .dlt { font-size:.64rem; font-weight:600; margin-left:3px; white-space:nowrap; }
          .cv-tile svg { display:block; width:100%; height:22px; margin-top:1px; }

          /* Role leaders */
          .cv-lead { display:flex; justify-content:space-between; align-items:center;
            padding:2px 0; border-bottom:1px solid #F3F0F9; }
          .cv-lead:last-child { border-bottom:none; }
          .cv-lead .role { color:#7C3AED; font-size:.6rem; text-transform:uppercase;
            letter-spacing:.06em; font-weight:700; }
          .cv-lead .name { font-weight:600; font-size:.84rem; color:#1F2937; line-height:1.2; }
          .cv-lead .num { text-align:right; font-weight:700; color:#2A0A4A; font-size:.95rem; line-height:1.1; }
          .cv-lead .num small { display:block; color:#9CA3AF; font-weight:500; font-size:.62rem; }

          /* Compact segmented controls */
          div[data-testid="stButtonGroup"] button { min-height:28px; padding:2px 9px; }
          div[data-testid="stButtonGroup"] button p { font-size:.74rem; }

          div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { min-height:30px; font-size:.8rem; }

          /* Streamlit pulls markdown blocks up by 1rem; not wanted for these. */
          div[data-testid="stMarkdownContainer"]:has(> .cv-band),
          div[data-testid="stMarkdownContainer"]:has(> .cv-tiles),
          div[data-testid="stMarkdownContainer"]:has(> .wa-head),
          div[data-testid="stMarkdownContainer"]:has(> .wa-insight),
          div[data-testid="stMarkdownContainer"]:has(> .card-title),
          div[data-testid="stMarkdownContainer"]:has(> .cv-lead),
          div[data-testid="stMarkdownContainer"]:has(> .tp) { margin-bottom:0 !important; }

          /* Opponents grid (deep dive) */
          .op-wrap { max-height:470px; overflow-y:auto; margin-bottom:12px; }
          .op-grid { width:100%; border-collapse:collapse; font-size:.8rem; }
          .op-grid th { text-align:left; font-size:.64rem; text-transform:uppercase; letter-spacing:.07em;
            color:#6D28D9; padding:4px 6px; border-bottom:1px solid #E7E3EF; position:sticky; top:0; background:#fff; }
          .op-grid td { padding:4px 6px; border-bottom:1px solid #F3F0F9; vertical-align:middle; }
          .op-name { font-weight:600; white-space:nowrap; }
          .op-num { font-weight:700; color:#2A0A4A; white-space:nowrap; }
          .op-chip { display:inline-block; color:#fff; border-radius:4px; padding:1px 6px; margin:1px 3px 1px 0;
            font-size:.7rem; font-weight:600; white-space:nowrap; }

          /* Window-size reporter: no visible footprint */
          div[data-testid="stElementContainer"]:has(iframe[title*="viewport"]) {
            position:absolute; width:0; height:0; overflow:hidden; margin:0; }

          /* Login */
          .login-head { margin:18vh 0 14px; text-align:center; }
          .login-head b { display:block; font-size:1.4rem; color:#2A0A4A; }
          .login-head span { color:#6B7280; font-size:.9rem; }

          @media (max-width: 1380px) { .cv-band .opt { display:none; } }

          /* Match mode */
          .cv-res { font-style:normal; font-size:.8rem; padding:2px 8px; border-radius:5px; }
          .tp { display:flex; flex-direction:column; gap:4px; margin-top:2px; }
          .tp-row { display:grid; grid-template-columns:118px 46px 1fr 46px; align-items:center; gap:8px; }
          .tp-f, .tp-o { font-weight:700; font-size:.85rem; color:#2A0A4A; }
          .tp-f { text-align:right; } .tp-o { color:#9A4A0E; }
          .tp-lbl { font-size:.72rem; color:#4B5563; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .tp-bar { position:relative; height:9px; border-radius:5px; background:#C25E12; overflow:visible; }
          .tp-bar i { position:absolute; left:0; top:0; bottom:0; background:#7C3AED; border-radius:5px 0 0 5px; }
          .tp-bar em { position:absolute; top:-3px; width:2px; height:15px; background:#1F2937; margin-left:-1px; }

          /* Quarter-time check */
          .qt-big { font-size:2.6rem; font-weight:800; color:#2A0A4A; line-height:1; margin-top:6px; }
          .qt-sub { color:#6B7280; font-size:.85rem; margin:4px 0 10px; }
          .qt-line { font-size:.9rem; color:#1F2937; margin:3px 0; }
          .qt-line b { color:#4C1D95; }

          /* Wharf-ai panel */
          .wa-head { background:linear-gradient(100deg,#2A0A4A 0%,#4C1D95 70%,#6D28D9 100%);
            color:#fff; border-radius:8px; padding:7px 12px; display:flex; align-items:center; gap:9px; }
          .wa-head .dot { width:30px; height:30px; border-radius:50%; border:1.5px solid #fff; }
          .wa-head b { font-size:1rem; letter-spacing:.2px; }
          .wa-head span { display:block; font-size:.64rem; color:#C4B5FD; }
          .wa-insight { background:#F5F1FB; border-left:4px solid #7C3AED; border-radius:8px;
            padding:9px 11px; font-size:.82rem; line-height:1.4; color:#1F2937; }
          .wa-insight .tag { font-size:.6rem; font-weight:700; letter-spacing:.08em;
            text-transform:uppercase; color:#7C3AED; margin-bottom:3px; }
          .wa-insight b { color:#2A0A4A; }
          [data-testid="stChatMessage"] { padding:6px 4px; }
          [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li { font-size:.84rem; }

          div[data-testid="stButton"] button { min-height:30px; border-radius:8px; padding:4px 10px;
            justify-content:flex-start; text-align:left; }
          div[data-testid="stButton"] button p { font-size:.78rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card_title(text, note="", keys=None):
    """Card heading. keys: optional [(label, colour)] drawn as a legend, for
    charts too narrow for a Plotly legend."""
    note_html = f" <span>{html.escape(note)}</span>" if note else ""
    key_html = "".join(
        f'<span class="key"><i style="background:{c}"></i>{html.escape(l)}</span>'
        for l, c in (keys or []))
    st.markdown(f'<div class="card-title">{html.escape(text)}{note_html}{key_html}</div>',
                unsafe_allow_html=True)


def header_band(season, rec, form, data_note):
    """form: list of (result, tooltip) for the last five games."""
    chips = "".join(
        f'<i title="{html.escape(t)}" style="background:'
        f'{COLORS["win"] if r == "W" else COLORS["loss"]}">{r}</i>'
        for r, t in form)
    stats = [
        (f'{rec["wins"]}-{rec["losses"]}', "Record"),
        (f'{rec["win_pct"]:.0f}%', "Win rate"),
        (f'{rec["score_for"]:.1f}', "Avg for"),     # hidden on narrow windows
        (f'{rec["score_against"]:.1f}', "Avg against"),
        (f'{rec["margin"]:+.1f}', "Avg margin"),
    ]
    stat_html = "".join(
        f'<div class="cv-stat{" opt" if l.startswith("Avg ") and l != "Avg margin" else ""}">'
        f'<b>{v}</b><span>{l}</span></div>' for v, l in stats)
    st.markdown(
        f'<div class="cv-band"><div class="ttl">Fremantle {season}'
        f'<small>{html.escape(data_note)}</small></div>{stat_html}'
        f'<div class="cv-stat"><div class="cv-form">{chips}</div><span>Last 5</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _sparkline(values, labels, highlight=None):
    """Inline SVG sparkline with a hover title on every point. The game at index
    `highlight` (default: the last) is drawn in the accent colour."""
    vals = [v for v in values if v == v]
    if len(vals) < 2:
        return ""
    w, h, pad = 160, 22, 3
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    n = len(values)
    pts = {}  # index -> (x, y, value, label)
    for i, v in enumerate(values):
        if v == v:
            pts[i] = (pad + i * (w - 2 * pad) / (n - 1),
                      h - pad - (v - lo) / span * (h - 2 * pad), v, labels[i])
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in pts.values())
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="transparent">'
        f'<title>{html.escape(lbl)}: {v:g}</title></circle>'
        for x, y, v, lbl in pts.values())
    target = n - 1 if highlight is None else highlight
    lx, ly = (pts.get(target) or list(pts.values())[-1])[:2]
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
            f'<polyline points="{line}" fill="none" stroke="{COLORS["spark"]}" '
            f'stroke-width="1.5" vector-effect="non-scaling-stroke"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.5" fill="{COLORS["freo"]}"/>'
            f'{dots}</svg>')


def tiles_row(tiles, baseline):
    cells = []
    for t in tiles:
        v = t["value"]
        if v is None:
            val = "-"
        elif t["kind"] == "diff":
            val = f"{v:+.1f}"
        elif t["kind"] == "acc":
            val = f"{v:.1f}%"
        else:
            val = f"{v:.1f}"
        dlt = ""
        if t["change"] is not None:
            c = t["change"]
            arrow = "▲" if c > 0 else ("▼" if c < 0 else "→")
            if t["better"] is None or c == 0:
                color = COLORS["muted"]
            else:
                good = (c > 0) == t["better"]
                color = COLORS["win"] if good else COLORS["loss"]
            dlt = (f'<span class="dlt" style="color:{color}" '
                   f'title="{baseline}: {t["base"]:.1f}">{arrow} {c:+.1f}{t["unit"]}</span>')
        cells.append(
            f'<div class="cv-tile"><div class="lbl">{html.escape(t["label"])}</div>'
            f'<div class="val">{val}{dlt}</div>'
            f'{_sparkline(t["series"], t["games"], t.get("highlight"))}</div>')
    st.markdown(f'<div class="cv-tiles">{"".join(cells)}</div>', unsafe_allow_html=True)


def leaders_list(leaders):
    rows = ""
    for r in leaders:
        if "value" in r:  # a row with its own figure, e.g. top goalkicker
            val, small = r["value"], r["sub"]
        else:
            val = "-" if r["avg"] is None else f'{r["avg"]:.1f}'
            small = f'per game · led {r["led"]}/{r["games"]}'
        rows += (f'<div class="cv-lead"><div><div class="role">{html.escape(r["role"])}</div>'
                 f'<div class="name">{html.escape(r["player"])}</div></div>'
                 f'<div class="num">{html.escape(val)}<small>{html.escape(small)}</small>'
                 f'</div></div>')
    st.markdown(rows, unsafe_allow_html=True)


def _svg_data_uri(name):
    import base64, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)
    with open(path, "rb") as f:
        return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()


def chat_header():
    st.markdown(f'<div class="wa-head"><img class="dot" src="{_svg_data_uri("anchor.svg")}" alt="">'
                '<div><b>Wharf-ai</b>'
                '<span>Answers from the loaded match data only</span></div></div>',
                unsafe_allow_html=True)


def _md_bold(text):
    """Escape text and turn **bold** into <b> tags."""
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(text))


def insight_card(text):
    st.markdown(f'<div class="wa-insight"><div class="tag">Insight</div>{_md_bold(text)}</div>',
                unsafe_allow_html=True)


def match_band(game, venue_date):
    """Header band for match mode: result, score line and margin."""
    res = "Won" if game["result"] == "W" else "Lost"
    color = COLORS["win"] if game["result"] == "W" else COLORS["loss"]
    fq, oq = game["freo_qtrs"].split()[-1], game["opp_qtrs"].split()[-1]
    st.markdown(
        f'<div class="cv-band"><div class="ttl">{html.escape(game["round"])} v '
        f'{html.escape(game["opponent"])}<small>{html.escape(venue_date)}</small></div>'
        f'<div class="cv-stat"><b><i class="cv-res" style="background:{color}">{res}</i></b>'
        f'<span>{html.escape(game["type"])}</span></div>'
        f'<div class="cv-stat"><b>{fq} ({game["freo_score"]})</b><span>Fremantle</span></div>'
        f'<div class="cv-stat"><b>{oq} ({game["opp_score"]})</b><span>{html.escape(game["opponent"])}</span></div>'
        f'<div class="cv-stat opt"><b>{int(game["margin"]):+d}</b><span>Margin</span></div></div>',
        unsafe_allow_html=True)


def tape(rows):
    """Tale of the tape: one split bar per stat, Freo share (purple) against the
    opposition (orange), numbers either side, and a tick at Freo's season
    average share."""
    out = ""
    for r in rows:
        f = f'{r["freo"]:,.0f}'
        o = f'{r["opp"]:,.0f}'
        tip = (f'{r["stat"]}: Freo {f}, opp {o}. Season average share '
               f'{r["season_share"]:.0f}% (diff {r["season_diff"]:+.1f} a game)')
        out += (f'<div class="tp-row" title="{html.escape(tip)}">'
                f'<span class="tp-lbl">{html.escape(r["stat"])}</span><span class="tp-f">{f}</span>'
                f'<div class="tp-bar"><i style="width:{r["share"]:.1f}%"></i>'
                f'<em style="left:{r["season_share"]:.1f}%"></em></div>'
                f'<span class="tp-o">{o}</span></div>')
    st.markdown(f'<div class="tp">{out}</div>', unsafe_allow_html=True)
