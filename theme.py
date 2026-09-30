"""Colours, Plotly styling, CSS and HTML components for the Coach View.

Styled after the club website's look (flat deep purple #331C54 header and
navigation, #F7F7F7 page, white cards with a soft shadow, bold Inter headings
in sentence case, purple-to-maroon match card), without any club logo, crest,
photos or other trademarks. Data colours stay the validated pair below. The categorical pair (Freo purple,
opposition orange) was validated for lightness, chroma, colour-vision
separation and contrast on a light surface. Colour follows the entity (Freo is
always purple), never rank. No club logo or trademarks.
"""

import html

import streamlit as st

# Chart palette, derived from fremantlefc.com.au's colours and checked with the
# dataviz validator (OKLCH lightness band, chroma floor, colour-vision separation,
# contrast on white). The site purple #331C54 is too dark for a data mark
# (L 0.29, below the 0.43 floor), so Freo uses its exact hue lifted into the band;
# the opposition uses the site's cyan. Maroon (the site's match card) could not
# be the opposition: it is too close to the loss red (normal-vision dE 9.8).
COLORS = {
    "freo": "#61359C",     # Fremantle: site purple hue at OKLCH L 0.44 (categorical slot 1)
    "opp": "#008CA2",      # Opposition: site cyan hue at L 0.58 (slot 2; CVD dE 17 vs Freo)
    "series3": "#CC4C77",  # site maroon hue (slot 3, extra chart series only)
    "series4": "#2E5FB7",  # site navy hue (slot 4)
    "win": "#288B2C",      # site green, darkened for white text (4.4:1)
    "loss": "#D42325",     # site "FULL TIME" red, adjusted (5.2:1 with white text)
    "ink": "#1A1A1A",      # site text
    "muted": "#525252",    # site secondary text
    "neutral": "#A3A3A3",  # de-emphasis marks (negative bars, "their opponent")
    "grid": "#E6E6E6",     # site rule lines
    "brand": "#331C54",    # site purple (header band, nav, darkest ramp step)
    "spark": "#B7A8D8",    # sparkline line, light step of the brand hue
}
# One-hue sequential ramp, light to dark, ending at the site purple (validated:
# monotone lightness, visible steps, light end >= 2:1 on white).
RAMP = ["#BEACE4", "#9F86CF", "#8061B5", "#5E3E8F", "#331C54"]
# Diverging: opposition cyan <- neutral grey -> Freo purple.
DIVERGE = [COLORS["opp"], "#81C4D1", "#EDEDEF", "#B8A6DD", COLORS["freo"]]
SERIES = [COLORS["freo"], COLORS["opp"], COLORS["series3"], COLORS["series4"]]

# Club colours for the Scout view: colours only, no logos or other marks.
# chart: the club's hue, with the lightness and chroma closest to the club colour that
#   still passes the dataviz validator against Freo #61359C (CVD dE >= 8, normal dE >= 15,
#   lightness band, chroma floor) and against the grey used for their opponents.
# band / accent: the club's dark colour (white text) and a second club colour.
# vs: the grey for 'their opponent' (lighter for Collingwood, whose chart colour is charcoal).
CLUB_COLOURS = {
    "Adelaide": {"chart": "#0064D2", "band": "#002B5C", "accent": "#E21937"},
    "Brisbane Lions": {"chart": "#8F204E", "band": "#6B0033", "accent": "#FDBE57"},
    "Carlton": {"chart": "#4D6ECC", "band": "#0E1E5B", "accent": "#FFFFFF"},
    "Collingwood": {"chart": "#3D3D3D", "band": "#111111", "accent": "#FFFFFF", "vs": "#C4C4C4"},
    "Essendon": {"chart": "#C52A35", "band": "#CC2031", "accent": "#111111"},
    "Geelong": {"chart": "#0064D2", "band": "#002B5C", "accent": "#FFFFFF"},
    "Gold Coast": {"chart": "#D33D2D", "band": "#D9261C", "accent": "#F6BD00"},
    "Greater Western Sydney": {"chart": "#EE5D27", "band": "#343434", "accent": "#F15C22"},
    "Hawthorn": {"chart": "#895700", "band": "#4D2004", "accent": "#FBBF15"},
    "Melbourne": {"chart": "#6973BB", "band": "#0F1131", "accent": "#CC2031"},
    "North Melbourne": {"chart": "#2766DB", "band": "#013B9F", "accent": "#FFFFFF"},
    "Port Adelaide": {"chart": "#0088A9", "band": "#061A33", "accent": "#00A1C9"},
    "Richmond": {"chart": "#C5A100", "band": "#111111", "accent": "#FED102"},
    "St Kilda": {"chart": "#DA4434", "band": "#111111", "accent": "#ED0F05"},
    "Sydney": {"chart": "#DA433B", "band": "#D71920", "accent": "#FFFFFF"},
    "West Coast": {"chart": "#2766DB", "band": "#003087", "accent": "#F2A900"},
    "Western Bulldogs": {"chart": "#0064D3", "band": "#014896", "accent": "#BD002B"},
}


def club_colours(club):
    """A club's colours, falling back to the default opposition colour."""
    c = CLUB_COLOURS.get(club, {})
    return {"chart": c.get("chart", COLORS["opp"]), "band": c.get("band", COLORS["brand"]),
            "accent": c.get("accent", "#FFFFFF"), "vs": c.get("vs", COLORS["neutral"])}

FONT = "Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"


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
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
          :root { --brand:#331C54; --brand-2:#4A2A78; --maroon:#8B0042; --ink:#1A1A1A;
                  --muted:#525252; --line:#E6E6E6; --canvas:#F7F7F7;
                  --freo:#61359C; --opp:#008CA2; }
          html, body, .stApp, .stApp button, .stApp input, .stApp textarea, .stApp select,
          .stApp [data-testid="stMarkdownContainer"], .stApp [data-baseweb] {
            font-family:Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
          .stApp { background:var(--canvas); color:var(--ink); }

          /* One screen: no Streamlit chrome, tight padding and gaps. */
          header[data-testid="stHeader"], footer:not(.driver-popover-footer), #MainMenu,
          [data-testid="stToolbar"], [data-testid="stDecoration"],
          section[data-testid="stSidebar"], [data-testid="collapsedControl"] { display:none !important; }
          .block-container { padding:8px 14px 0 !important; max-width:100% !important; }
          div[data-testid="stVerticalBlock"] { gap:6px; }
          div[data-testid="stHorizontalBlock"] { gap:8px; }
          div[data-testid="stElementContainer"]:has(> .stPlotlyChart) { margin:0; }

          /* Cards: keyed containers (st-key-card_*), plus the older wrapper name */
          div[class*="st-key-card_"],
          div[data-testid="stVerticalBlockBorderWrapper"] {
            background:#FFFFFF; border:1px solid var(--line) !important; border-radius:8px;
            box-shadow:0 1px 3px rgba(0,0,0,.07);
          }
          div[class*="st-key-card_"] { gap:2px; }
          div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] { gap:2px; }
          .st-key-deep_dive [data-baseweb="select"] * { font-size:.8rem; }
          .card-title {
            font-size:.82rem; font-weight:700; letter-spacing:-.2px; color:var(--ink);
            margin:0; line-height:1.35; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
          }
          .card-title span { color:var(--muted); font-weight:400; font-size:.75rem; letter-spacing:0; }
          .card-title .key { color:var(--muted); margin-left:8px; white-space:nowrap; font-size:.75rem; font-weight:500; }
          .card-take, .card-title .take { display:block; font-size:.8rem; font-weight:600; color:var(--brand);
            line-height:1.35; margin:0 0 4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
            letter-spacing:0; }
          .card-title .key i { display:inline-block; width:9px; height:9px; border-radius:2px;
            margin-right:4px; vertical-align:-1px; }

          /* Header band */
          .cv-band {
            background:var(--brand);
            color:#fff; border-radius:8px; padding:7px 14px; height:52px;
            display:flex; align-items:center; gap:clamp(10px, 1.2vw, 22px); overflow:hidden;
          }
          .cv-band .ttl { font-weight:800; font-size:1.08rem; letter-spacing:-.3px; white-space:nowrap; }
          .cv-band .ttl small { display:block; font-weight:500; font-size:.75rem; letter-spacing:0;
            color:rgba(255,255,255,.72); }
          .cv-band.match { background:linear-gradient(100deg, var(--brand) 0%, var(--brand-2) 55%, var(--maroon) 100%); }
          .cv-stat { line-height:1.05; white-space:nowrap; }
          .cv-stat b { font-size:1.08rem; font-weight:700; }
          .cv-stat span { display:block; font-size:.75rem; letter-spacing:0;
            color:rgba(255,255,255,.75); }
          .cv-stat.hero b { font-size:1.75rem; font-weight:800; letter-spacing:-.8px; line-height:1; }
          .cv-form { display:flex; gap:3px; }
          .cv-form i { font-style:normal; font-size:.75rem; font-weight:700; width:20px;
            height:20px; border-radius:4px; display:flex; align-items:center;
            justify-content:center; color:#fff; box-shadow:0 0 0 1.5px rgba(255,255,255,.9); }

          /* Headline tiles */
          .cv-tiles { margin:2px 0 8px; display:grid; grid-template-columns:repeat(var(--n, 6), 1fr); gap:8px; }
          .cv-tile { background:#fff; border:1px solid var(--line); border-radius:8px;
            padding:6px 8px 4px; min-width:0; box-shadow:0 1px 3px rgba(0,0,0,.07); }
          .cv-tile .lbl { font-size:.75rem; font-weight:600; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .cv-tile .val { font-size:1.4rem; font-weight:800; letter-spacing:-.4px; color:var(--ink); line-height:1.15; }
          .cv-tile .dlt { font-size:.75rem; font-weight:600; margin-left:3px; white-space:nowrap; }
          .cv-tile svg { display:block; width:100%; height:22px; margin-top:1px; }

          /* Role leaders */
          .cv-lead { display:grid; grid-template-columns:auto 1fr auto; align-items:baseline; gap:8px;
            padding:4px 0; border-bottom:1px solid #EFEFEF; }
          .cv-lead .role { white-space:nowrap; }
          .cv-lead .name { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .cv-lead:last-child { border-bottom:none; }
          .cv-lead .role { color:var(--brand); font-size:.75rem; font-weight:700; letter-spacing:0; }
          .cv-lead .name { font-weight:700; font-size:.84rem; color:var(--ink); line-height:1.2; letter-spacing:-.1px; }
          .cv-lead .num { text-align:right; font-weight:800; color:var(--ink); font-size:.95rem; line-height:1.1; }
          .cv-lead .num small { display:block; color:var(--muted); font-weight:400; font-size:.75rem; white-space:nowrap; }

          /* Compact segmented controls */
          div[data-testid="stButtonGroup"] button { min-height:28px; padding:2px 7px; }
          div[data-testid="stButtonGroup"] button p { font-size:.75rem; }

          div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { min-height:30px; font-size:.8rem; }

          /* Streamlit pulls markdown blocks up by 1rem; not wanted for these. */
          div[data-testid="stMarkdownContainer"]:has(> .cv-band),
          div[data-testid="stMarkdownContainer"]:has(> .cv-tiles),
          div[data-testid="stMarkdownContainer"]:has(> .wa-head),
          div[data-testid="stMarkdownContainer"]:has(> .wa-insight),
          div[data-testid="stMarkdownContainer"]:has(> .card-title),
          div[data-testid="stMarkdownContainer"]:has(> .cv-lead),
          div[data-testid="stMarkdownContainer"]:has(> .tp),
          div[data-testid="stMarkdownContainer"]:has(> .wa-sub) { margin-bottom:0 !important; }

          /* Opponents grid (deep dive) */
          .op-wrap { max-height:470px; overflow-y:auto; margin-bottom:12px; }
          .op-grid { width:100%; border-collapse:collapse; font-size:.8rem; }
          .op-grid th { text-align:left; font-size:.75rem; text-transform:uppercase; letter-spacing:.07em;
            color:var(--brand); padding:4px 6px; border-bottom:1px solid var(--line); position:sticky; top:0; background:#fff; }
          .op-grid td { padding:4px 6px; border-bottom:1px solid #EFEFEF; vertical-align:middle; }
          .op-name { font-weight:600; white-space:nowrap; }
          .op-num { font-weight:700; color:var(--ink); white-space:nowrap; }
          .op-chip { display:inline-block; color:#fff; border-radius:4px; padding:1px 6px; margin:1px 3px 1px 0;
            font-size:.7rem; font-weight:600; white-space:nowrap; }

          /* Window-size reporter: no visible footprint */
          div[data-testid="stElementContainer"]:has(iframe[title*="viewport"]),
          div[data-testid="stElementContainer"]:has(iframe[title*="tour"]) {
            position:absolute; width:0; height:0; overflow:hidden; margin:0; }

          /* Login */
          .login-head { margin:18vh 0 14px; text-align:center; }
          .login-head b { display:block; font-size:1.5rem; font-weight:800; letter-spacing:-.5px; color:var(--ink); }
          .login-head span { color:var(--muted); font-size:.9rem; }

          @media (max-width: 1760px) { .cv-band .opt { display:none; } }
          @media (max-width: 1500px) {
            .cv-band.match { gap:12px; padding:7px 11px; }
            .cv-band.match .cv-stat b { font-size:.98rem; } .cv-band.match .ttl { font-size:1rem; } }
          @media (max-width: 1380px) { .cv-band { gap:9px; padding:7px 10px; }
            .cv-band .cv-stat b { font-size:.94rem; } .cv-band .ttl { font-size:.98rem; }
            .cv-band.match .ttl small { display:none; } }

          /* Match mode */
          .cv-res { font-style:normal; font-size:.75rem; font-weight:700; padding:2px 9px; border-radius:999px;
            text-transform:uppercase; letter-spacing:.04em; }
          .tp { display:flex; flex-direction:column; gap:2px; margin-top:0; }
          .tp-row { display:grid; grid-template-columns:118px 46px 1fr 46px; align-items:center; gap:8px; }
          .tp-f, .tp-o { font-weight:800; font-size:.85rem; color:var(--ink); }
          .tp-f { text-align:right; }
          .tp-lbl { font-size:.75rem; font-weight:500; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .tp-bar { position:relative; height:9px; border-radius:5px; background:var(--opp); overflow:visible; }
          .tp-bar i { position:absolute; left:0; top:0; bottom:0; background:var(--freo); border-radius:5px 0 0 5px;
            border-right:2px solid #fff; }
          .tp-bar em { position:absolute; top:-3px; width:2px; height:15px; background:var(--ink); margin-left:-1px; }

          /* Scout report */
          .cv-tile .rk { font-size:.75rem; font-weight:700; color:#fff; background:var(--brand);
            border-radius:999px; padding:1px 7px; margin-left:6px; vertical-align:2px; letter-spacing:0; }
          .cv-tile .fr { font-size:.75rem; color:var(--muted); margin-top:3px; }

          /* Quarter-time check */
          .qt-big { font-size:2.6rem; font-weight:800; letter-spacing:-1px; color:var(--ink); line-height:1; margin-top:6px; }
          .qt-sub { color:var(--muted); font-size:.85rem; margin:4px 0 10px; }
          .qt-line { font-size:.9rem; color:var(--ink); margin:3px 0; }
          .qt-line b { color:var(--brand); }

          /* Wharf-ai panel */
          .wa-head { background:var(--brand);
            color:#fff; border-radius:8px; padding:7px 12px; display:flex; align-items:center; gap:9px; }
          .wa-head .dot { width:30px; height:30px; border-radius:50%; border:1.5px solid #fff; }
          .wa-head b { font-size:1rem; font-weight:800; letter-spacing:-.2px; }
          .wa-head span { display:block; font-size:.75rem; color:rgba(255,255,255,.72); }
          .wa-insight { background:#F4F1F8; border-left:4px solid var(--brand); border-radius:8px;
            padding:9px 11px; font-size:.82rem; line-height:1.4; color:var(--ink); }
          .wa-insight .tag { font-size:.75rem; font-weight:700; letter-spacing:.08em;
            text-transform:uppercase; color:var(--brand); margin-bottom:3px; }
          .wa-insight b { color:var(--ink); }
          [data-testid="stChatMessage"] { padding:6px 4px; }
          [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li { font-size:.84rem; }

          div[data-testid="stButton"] button { min-height:30px; border-radius:8px; padding:4px 10px;
            justify-content:flex-start; text-align:left; background:#fff; border:1px solid var(--line); }
          div[data-testid="stButton"] button:hover { border-color:var(--brand); color:var(--brand); }
          div[data-testid="stButton"] button p { font-size:.78rem; font-weight:500; text-align:left; }
          div[data-testid="stButton"] button > div { justify-content:flex-start; width:100%; }
          div[data-testid="stButton"] button[kind="tertiary"] { border:none; background:transparent; }
          div[data-testid="stButton"] button[kind="primary"] { background:var(--brand); border-color:var(--brand); color:#fff; }
          .wa-sub { font-size:.75rem; font-weight:700; color:var(--muted); margin:6px 0 2px; }
          .wa-earlier { border-top:1px solid var(--line); padding-top:8px; margin-top:10px; }
          .st-key-wa_history div[data-testid="stElementContainer"]:has(iframe[height="0"]) {
            position:absolute; width:0; height:0; overflow:hidden; margin:0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card_title(text, note="", keys=None, takeaway=""):
    """Card heading. keys: optional [(label, colour)] drawn as a legend, for
    charts too narrow for a Plotly legend. takeaway: the card's main point in
    one line, shown under the title."""
    note_html = f" <span>{html.escape(note)}</span>" if note else ""
    key_html = "".join(
        f'<span class="key"><i style="background:{c}"></i>{html.escape(l)}</span>'
        for l, c in (keys or []))
    take_html = f'<b class="take" title="{html.escape(takeaway)}">{html.escape(takeaway)}</b>' \
        if takeaway else ""
    st.markdown(f'<div class="card-title">{html.escape(text)}{note_html}{key_html}{take_html}</div>',
                unsafe_allow_html=True)


def header_band(season, rec, form, data_note):
    """form: list of (result, tooltip) for the last five games."""
    chips = "".join(
        f'<i title="{html.escape(t)}" style="background:'
        f'{COLORS["win"] if r == "W" else COLORS["loss"]}">{r}</i>'
        for r, t in form)
    stats = [
        (f'{rec["wins"]}-{rec["losses"]}', "Record"),        # the lead number
        (f'{rec["win_pct"]:.0f}%', "Win rate"),
        (f'{rec["score_for"]:.1f}', "Avg for"),     # hidden on narrow windows
        (f'{rec["score_against"]:.1f}', "Avg against"),
        (f'{rec["margin"]:+.1f}', "Avg margin"),
    ]
    stat_html = "".join(
        f'<div class="cv-stat{" hero" if l == "Record" else ""}'
        f'{" opt" if (l.startswith("Avg ") and l != "Avg margin") or l == "Win rate" else ""}">'
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


def tiles_row(tiles, baseline, rank_label=None):
    """Headline tiles. rank_label: show each tile's rank chip (player tiles)."""
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
        rk = ""
        if rank_label and t.get("rank"):
            rk = (f'<span class="rk" title="{rank_label}: {t["rank"]} of {t["squad"]}">'
                  f'{_ordinal(t["rank"])}</span>')
        cells.append(
            f'<div class="cv-tile"><div class="lbl">{html.escape(t["label"])}</div>'
            f'<div class="val">{val}{rk}{dlt}</div>'
            f'{_sparkline(t["series"], t["games"], t.get("highlight"))}</div>')
    st.markdown(f'<div class="cv-tiles" style="--n:{len(cells)}">{"".join(cells)}</div>',
                unsafe_allow_html=True)


def leaders_list(leaders):
    """One compact line per leader: role, name, number. The detail (a game,
    games led) is in the hover so the list fits its card at 12px."""
    rows = ""
    for r in leaders:
        if "value" in r:  # a row with its own figure, e.g. top goalkicker
            val, small = r["value"], r["sub"]
        else:
            val = "-" if r["avg"] is None else f'{r["avg"]:.1f}'
            small = f'{val} a game · led {r["led"]} of {r["games"]} games'
        rows += (f'<div class="cv-lead" title="{html.escape(r["role"])}: {html.escape(r["player"])}, '
                 f'{html.escape(small)}"><span class="role">{html.escape(r["role"])}</span>'
                 f'<span class="name">{html.escape(r["player"])}</span>'
                 f'<span class="num">{html.escape(val)}</span></div>')
    st.markdown(rows, unsafe_allow_html=True)


def _svg_data_uri(name):
    import base64, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)
    with open(path, "rb") as f:
        return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode()


def chat_header(note="Answers from the loaded match data only"):
    st.markdown(f'<div class="wa-head"><img class="dot" src="{_svg_data_uri("anchor.svg")}" alt="">'
                f'<div><b>Wharf-ai</b><span>{html.escape(note)}</span></div></div>',
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
        f'<div class="cv-band match"><div class="ttl">{html.escape(game["round"])} v '
        f'{html.escape(game["opponent"])}<small>{html.escape(venue_date)}</small></div>'
        f'<div class="cv-stat opt"><b><i class="cv-res" style="background:{color}">{res}</i></b>'
        f'<span>{html.escape(game["type"])}</span></div>'
        f'<div class="cv-stat"><b>{fq} ({game["freo_score"]})</b><span>Fremantle</span></div>'
        f'<div class="cv-stat"><b>{oq} ({game["opp_score"]})</b><span>{html.escape(game["opponent"])}</span></div>'
        f'<div class="cv-stat hero"><b>{int(game["margin"]):+d}</b><span>Margin</span></div></div>',
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


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def scout_band(team, season, lad_row, last5):
    """Header band for the scout report: record, ladder spot, percentage, form."""
    chips = "".join(
        f'<i title="{html.escape(t)}" style="background:'
        f'{COLORS["win"] if r == "W" else COLORS["loss"]}">{r}</i>' for r, t in last5)
    stats = [
        (f'{int(lad_row["wins"])}-{int(lad_row["losses"])}' +
         (f'-{int(lad_row["draws"])}' if lad_row["draws"] else ""), "H&A"),
        (_ordinal(int(lad_row["position"])), "Ladder"),
    ]
    stat_html = "".join(f'<div class="cv-stat{" hero" if l == "Ladder" else " opt"}"><b>{v}</b>'
                        f'<span>{l}</span></div>' for v, l in stats)
    club = club_colours(team)
    st.markdown(
        f'<div class="cv-band match club" style="background:{club["band"]};'
        f'border-left:6px solid {club["accent"]}"><div class="ttl">Scout: {html.escape(team)}'
        f'<small>{season} · percentage {lad_row["pct"]:.1f} (home and away)</small></div>{stat_html}'
        f'<div class="cv-stat"><div class="cv-form">{chips}</div><span>Last 5</span></div></div>',
        unsafe_allow_html=True)


def scout_tiles_row(tiles, chip=None):
    """Opponent tiles: their value, league rank (chip in the club's colour), and
    Freo's value for comparison."""
    cells = []
    style = f' style="background:{chip}"' if chip else ""
    for t in tiles:
        rank = (f'<span class="rk"{style}>{_ordinal(t["rank"])}</span>' if t["rank"] else "")
        cells.append(
            f'<div class="cv-tile"><div class="lbl">{html.escape(t["label"])}</div>'
            f'<div class="val">{t["value"]}{rank}</div>'
            f'<div class="fr">Freo {t["freo"]}</div></div>')
    st.markdown(f'<div class="cv-tiles">{"".join(cells)}</div>', unsafe_allow_html=True)


def h2h_table(rows):
    """Freo's games against one club: result chip, score and two key counts."""
    body = ""
    for r in rows.itertuples():
        color = COLORS["win"] if r.result == "W" else COLORS["loss"]
        body += (f'<tr><td>{r.season} {html.escape(r.round)}</td><td>{html.escape(r.venue)}</td>'
                 f'<td><span class="op-chip" style="background:{color}">{r.result} '
                 f'{int(r.margin):+d}</span></td><td class="op-num">{r.freo_score}-{r.opp_score}</td>'
                 f'<td>{int(r.freo_inside_50s - r.opp_inside_50s):+d}</td>'
                 f'<td>{int(r.freo_contested_poss - r.opp_contested_poss):+d}</td></tr>')
    st.markdown('<table class="op-grid"><thead><tr><th>Game</th><th>Venue</th><th>Result</th>'
                '<th>Score</th><th>I50 diff</th><th>CP diff</th></tr></thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)


def player_band(player, season, me, hero_label="Disposals", hero_col="disposals"):
    """Header band for a player: games, the lead average, goals and time on ground."""
    games = len(me)
    goals = int(me["goals"].sum()) if "goals" in me else 0
    tog = me["time_on_ground_pct"].mean() if "time_on_ground_pct" in me else None
    jumper = int(me["jumper"].iloc[-1]) if games and "jumper" in me else None
    stats = [(f"{me[hero_col].mean():.1f}" if games else "-", f"{hero_label} a game", True),
             (str(games), "Games", False), (str(goals), "Goals", False)]
    if tog is not None and tog == tog:
        stats.append((f"{tog:.0f}%", "Time on ground", False))
    stat_html = "".join(f'<div class="cv-stat{" hero" if hero else ""}{" opt" if l == "Time on ground" else ""}">'
                        f'<b>{v}</b><span>{l}</span></div>' for v, l, hero in stats)
    sub_line = f"#{jumper} · {season} season" if jumper else f"{season} season"
    st.markdown(f'<div class="cv-band"><div class="ttl">{html.escape(player)}<small>'
                f'{html.escape(sub_line)}</small></div>{stat_html}</div>', unsafe_allow_html=True)
