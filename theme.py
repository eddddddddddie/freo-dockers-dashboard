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
import re

import streamlit as st

import marks

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

def result_colour(result):
    """Win green, loss red, a draw grey (every chip also carries its letter)."""
    return {"W": COLORS["win"], "L": COLORS["loss"]}.get(result, COLORS["neutral"])


def record_text(wins, losses, draws=0):
    """'12-10', or '12-10-1' with a draw."""
    return f"{int(wins)}-{int(losses)}" + (f"-{int(draws)}" if draws else "")


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
    """Shared chart look, after Tufte: no gridlines and no axis lines (only lines
    that mean something are drawn, per chart: a zero margin, an average, a
    median), muted tick labels, a single y axis (never dual-axis)."""
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
    fig.update_xaxes(showgrid=False, showline=False, zeroline=False,
                     tickfont=dict(color=COLORS["muted"]))
    fig.update_yaxes(title=dict(text=y_title, font=dict(color=COLORS["muted"], size=11)),
                     showgrid=False, showline=False, zeroline=False,
                     tickfont=dict(color=COLORS["muted"]))
    return fig


def inject_css():
    st.markdown(f'<style>:root {{ --mark-freo:{marks.uri("Fremantle")}; }}</style>',
                unsafe_allow_html=True)
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Source+Serif+4:ital,opsz,wght@0,8..60,600;1,8..60,600&display=swap');
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
          .block-container { padding:0 14px 0 !important; max-width:100% !important; }
          div[data-testid="stVerticalBlock"] { gap:6px; }
          div[data-testid="stHorizontalBlock"] { gap:8px; }
          div[data-testid="stElementContainer"]:has(> .stPlotlyChart) { margin:0; }

          /* The top bar, after the club site's nav bar: flat purple, edge to edge,
             the title in a serif, seasons and views as white nav links with an
             underline on the one selected, outlined icon buttons. */
          [data-testid="stLayoutWrapper"]:has(> .st-key-topbar) { margin:0 -14px 2px;
            width:auto !important; max-width:none !important; align-self:stretch; }
          .st-key-topbar { background:var(--brand); padding:2px 14px; width:100% !important;
            border-bottom:1px solid rgba(255,255,255,.14); }
          /* The CSS blocks above the bar take no room (no gap above it). */
          .block-container div[data-testid="stElementContainer"]:has(> .stMarkdown [data-testid="stMarkdownContainer"] > style:only-child) {
            position:absolute; width:0; height:0; overflow:hidden; }
          .cv-brand { font-family:"Source Serif 4", Georgia, "Times New Roman", serif; font-weight:600;
            font-size:1.5rem; line-height:1; color:#fff; letter-spacing:-.5px; white-space:nowrap;
            overflow:hidden; text-overflow:ellipsis; }
          .cv-brand i { font-style:italic; }
          .st-key-topbar [data-testid="stButtonGroup"] > div { gap:2px; }
          .st-key-topbar [data-testid="stButtonGroup"] button { background:transparent !important;
            border:none !important; border-radius:0 !important; box-shadow:none !important;
            min-height:36px; padding:2px 9px; }
          .st-key-topbar [data-testid="stButtonGroup"] button p { color:rgba(255,255,255,.78);
            font-weight:700; font-size:.88rem; }
          .st-key-topbar [data-testid="stButtonGroup"] button:hover { background:rgba(255,255,255,.08) !important; }
          .st-key-topbar [data-testid="stButtonGroup"] button[aria-checked="true"] {
            box-shadow:inset 0 -3px 0 #fff !important; }
          .st-key-topbar [data-testid="stButtonGroup"] button[aria-checked="true"] p { color:#fff; }
          .st-key-topbar div[data-testid="stButton"] button { background:transparent;
            border:1px solid rgba(255,255,255,.38); color:#fff; }
          .st-key-topbar div[data-testid="stButton"] button p { color:#fff; }
          .st-key-topbar div[data-testid="stButton"] button:hover { background:#fff; color:var(--brand); }
          .st-key-topbar div[data-testid="stButton"] button:hover p { color:var(--brand); }
          .st-key-topbar div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background:transparent; border-color:rgba(255,255,255,.38); color:#fff; }
          .st-key-topbar div[data-testid="stSelectbox"] svg { fill:#fff; }

          /* Cards: keyed containers (st-key-card_*), plus the older wrapper name */
          div[class*="st-key-card_"],
          div[data-testid="stVerticalBlockBorderWrapper"] {
            background:#FFFFFF; border:none !important; border-radius:4px; box-shadow:none;
          }   /* white on the light page is boundary enough: no border, no shadow */
          div[class*="st-key-card_"] { gap:2px; }
          div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] { gap:2px; }
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
            color:#fff; border-radius:4px; padding:7px 14px; height:52px;
            display:flex; align-items:center; gap:clamp(10px, 1.2vw, 22px); overflow:hidden;
          }
          /* The title block gives way (its subtitle ellipsises) so a band never overflows. */
          .cv-band .ttl { font-weight:800; font-size:1.08rem; letter-spacing:-.3px; white-space:nowrap;
            flex:0 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis; }
          .cv-band .ttl small { display:block; font-weight:500; font-size:.75rem; letter-spacing:0;
            color:rgba(255,255,255,.72); overflow:hidden; text-overflow:ellipsis; }
          .cv-band .cv-stat { flex:none; }
          .cv-band.match { background:linear-gradient(100deg, var(--brand) 0%, var(--brand-2) 55%, var(--maroon) 100%); }
          /* Match card (after the club site's): big score in the middle, thin dividers */
          .demo-pill { background:#E8A33D; color:#1A1A1A !important; }
          .mc-div { flex:none; width:1px; align-self:stretch; margin:-3px 0;
            background:rgba(255,255,255,.2); }
          .mc-score { display:flex; align-items:center; gap:10px; flex:none; }
          .mc-team { line-height:1.1; white-space:nowrap; text-align:right; }
          .mc-team.r { text-align:left; }
          .mc-team b { display:block; font-size:.8rem; font-weight:700; }
          .mc-team span { font-size:.75rem; color:rgba(255,255,255,.72); }
          .mc-num { font-size:1.75rem; font-weight:800; letter-spacing:-.8px; line-height:1; }
          .mc-score em, .mc-last em { font-style:normal; font-weight:500; color:rgba(255,255,255,.6); }
          /* The result pill and the game type under it, stacked with room between. */
          .mc-res { display:flex; flex-direction:column; align-items:flex-start; gap:4px; }
          .mc-res b { line-height:1; }
          .mc-res .cv-res { display:inline-block; font-size:.8rem; line-height:1.25; padding:2px 10px; }
          .mc-res span { line-height:1; }
          .mc-last b { font-size:1.08rem; }
          .mc-last .cv-res { padding:1px 7px; margin-left:3px; vertical-align:2px; }
          @media (max-width: 1599px) { .cv-band .opt2 { display:none; } }
          @media (max-width: 1380px) { .mc-team span { display:none; } .mc-num { font-size:1.5rem; } }
          /* A faint mark at the right of each band, where the club site puts its
             crests: our own line drawings (marks.py), the anchor for Freo and a
             club's mascot in its Scout band and at their end of the Match band. */
          .cv-band { position:relative; --mark:var(--mark-freo); }
          .cv-band::after { content:""; position:absolute; right:14px; top:-8px; width:80px; height:80px;
            background:var(--mark) no-repeat center/contain; opacity:.08; pointer-events:none; }
          .cv-band.club::after, .cv-band.match::after { right:24px; }
          .cv-stat { line-height:1.05; white-space:nowrap; }
          .cv-stat b { font-size:1.08rem; font-weight:700; }
          .cv-stat span { display:block; font-size:.75rem; letter-spacing:.04em; text-transform:uppercase;
            color:rgba(255,255,255,.75); }
          .cv-stat.hero b { font-size:1.75rem; font-weight:800; letter-spacing:-.8px; line-height:1; }
          .cv-form { display:flex; gap:3px; }
          .cv-form i { font-style:normal; font-size:.75rem; font-weight:700; width:20px;
            height:20px; border-radius:4px; display:flex; align-items:center;
            justify-content:center; color:#fff; box-shadow:0 0 0 1.5px rgba(255,255,255,.9); }

          /* Headline tiles */
          .cv-tiles { margin:2px 0 8px; display:grid; grid-template-columns:repeat(var(--n, 6), 1fr); gap:8px; }
          .cv-tile { background:#fff; border:none; border-radius:4px;
            padding:6px 8px 4px; min-width:0; box-shadow:none; }
          .cv-tile .lbl { font-size:.75rem; font-weight:700; color:var(--muted); white-space:nowrap; overflow:hidden;
            text-overflow:ellipsis; text-transform:uppercase; letter-spacing:.04em; }
          .cv-tile .val { font-size:1.4rem; font-weight:800; letter-spacing:-.4px; color:var(--ink); line-height:1.15; }
          .cv-tile .dlt { font-size:.75rem; font-weight:600; margin-left:3px; white-space:nowrap; }
          .cv-tile svg { display:block; width:100%; height:22px; margin-top:1px; }
          /* Narrow windows: value, rank chip and change stay on one line. */
          .cv-tile .val { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          @media (max-width: 1380px) { .cv-tile .val { font-size:1.22rem; letter-spacing:-.6px; }
            .cv-tile .dlt { margin-left:1px; letter-spacing:-.2px; } }

          /* Role leaders */
          .cv-lead { display:grid; grid-template-columns:auto 1fr auto; align-items:baseline; gap:8px;
            padding:4px 0; border-bottom:1px solid #EFEFEF; }
          .cv-lead .role { white-space:nowrap; }
          .cv-lead .name { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .cv-lead:last-child { border-bottom:none; }
          /* Match leaders, both sides */
          .lp-row { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1.15fr) minmax(0, 1.15fr);
            gap:8px; align-items:baseline; padding:3px 0; border-bottom:1px solid #EFEFEF; }
          .lp-row:last-child { border-bottom:none; }
          .lp-head { padding:0 0 3px; }
          .lp-side { font-size:.75rem; font-weight:700; color:var(--freo); white-space:nowrap;
            overflow:hidden; text-overflow:ellipsis; }
          .lp-role { color:var(--brand); font-size:.75rem; font-weight:700; white-space:nowrap;
            overflow:hidden; text-overflow:ellipsis; }
          .lp-cell { display:flex; justify-content:space-between; gap:4px; min-width:0; }
          .lp-n { font-weight:700; font-size:.82rem; color:var(--ink); white-space:nowrap;
            overflow:hidden; text-overflow:ellipsis; }
          .lp-v { font-weight:800; font-size:.9rem; }
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
          div[data-testid="stMarkdownContainer"]:has(> .cv-brand),
          div[data-testid="stMarkdownContainer"]:has(> .cv-tiles),
          div[data-testid="stMarkdownContainer"]:has(> .wa-head),
          div[data-testid="stMarkdownContainer"]:has(> .wa-insight),
          div[data-testid="stMarkdownContainer"]:has(> .wa-rot),
          div[data-testid="stMarkdownContainer"]:has(> .card-title),
          div[data-testid="stMarkdownContainer"]:has(> .cv-lead),
          div[data-testid="stMarkdownContainer"]:has(> .lp),
          div[data-testid="stMarkdownContainer"]:has(> .tp),
          div[data-testid="stMarkdownContainer"]:has(> .qt-box),
          div[data-testid="stMarkdownContainer"]:has(> .op-wrap),
          div[data-testid="stMarkdownContainer"]:has(> .wa-sub) { margin-bottom:0 !important; }

          /* Opponents grid (deep dive) */
          .op-wrap { overflow-y:auto; margin-bottom:8px; }
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
          div[data-testid="stElementContainer"]:has(iframe[title*="cookie"]),
          div[data-testid="stElementContainer"]:has(iframe[title*="tour"]) {
            position:absolute; width:0; height:0; overflow:hidden; margin:0; }

          /* Shown while the app waits for the window size on its first run */
          .cv-wait { margin:30vh 0 0; text-align:center; color:var(--muted); font-weight:600; }

          /* Login */
          /* Ticker (theme.ticker): one line scrolling right to left, edges faded */
          div[data-testid="stMarkdownContainer"]:has(> .tk) { margin-bottom:0 !important; }
          .tk { overflow:hidden; white-space:nowrap; color:#fff; font-size:.8rem;
            -webkit-mask-image:linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);
            mask-image:linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent); }
          .tk-track { display:flex; width:max-content; animation:tk-run linear infinite; }
          .tk:hover .tk-track { animation-play-state:paused; }
          .tk-track > div { display:flex; flex:none; }
          .tk-item { padding:0 22px; position:relative; color:rgba(255,255,255,.72); }
          .tk-item b { color:#fff; font-weight:700; margin-right:4px; }
          .tk-item::after { content:""; position:absolute; right:-3px; top:50%; width:5px; height:5px;
            margin-top:-2.5px; border-radius:50%; background:#D42325; }
          @keyframes tk-run { to { transform:translateX(-50%); } }
          .tk-bar { line-height:36px; }
          .tk-strip { line-height:28px; border-top:1px solid rgba(255,255,255,.14); margin:2px -14px 0;
            padding:0 4px; }
          .tk-login { line-height:42px; font-size:.9rem; margin:0 -14px 18px;
            border-top:1px solid rgba(255,255,255,.16); border-bottom:1px solid rgba(255,255,255,.16);
            background:rgba(0,0,0,.12); }
          /* Pinned along the bottom when there's room; on short windows (landscape
             phones) it stays in the page so it never covers the sign-in. */
          @media (min-height: 600px) {
            .tk-login { position:fixed; left:0; right:0; bottom:0; z-index:5; margin:0; border-bottom:none; } }
          .tk-login .tk-item { color:rgba(255,255,255,.85); font-weight:600; }
          @media (prefers-reduced-motion: reduce) { .tk-track { animation:none; } }

          /* Sign-in screen, after the club site's home page: the whole page purple,
             the headline, then the sign-in straight on the purple. */
          .stApp:has(.sp-hero) { background:
            radial-gradient(900px 520px at 88% 18%, rgba(139,0,66,.42), transparent 62%), var(--brand); }
          .stApp:has(.sp-hero)::after { content:""; position:fixed; right:-4vh; bottom:-6vh;
            width:62vh; height:62vh; background:var(--mark-freo) no-repeat center/contain;
            opacity:.045; pointer-events:none; }
          div[data-testid="stMarkdownContainer"]:has(> .sp-hero) { margin-bottom:0 !important; }
          .sp-hero { color:#fff; margin:0 -14px 22px; }
          .sp-top { display:flex; align-items:center; gap:14px; padding:9px 28px;
            border-bottom:1px solid rgba(255,255,255,.14); font-size:.75rem; }
          .sp-top b { text-transform:uppercase; letter-spacing:.14em; font-weight:800; }
          .sp-top span { color:rgba(255,255,255,.7); }
          .sp-title { font-family:"Source Serif 4", Georgia, serif; font-weight:600;
            font-size:clamp(2.4rem, 6.4vw, 5.4rem); line-height:1.02; letter-spacing:-.03em;
            padding:12vh 28px 0; }
          .sp-title span { display:inline-block; opacity:0; transform:translateY(18px);
            animation:sp-rise .6s cubic-bezier(.2,.7,.2,1) forwards; }
          .sp-title i { font-style:italic; }
          .sp-sub { display:flex; align-items:center; gap:10px; padding:16px 28px 0;
            font-size:1.05rem; color:rgba(255,255,255,.82); opacity:0;
            animation:sp-rise .6s .5s cubic-bezier(.2,.7,.2,1) forwards; }
          @keyframes sp-rise { to { opacity:1; transform:none; } }
          /* The sign-in: white fields and a white button on the purple */
          .st-key-login_card { max-width:400px; margin-left:14px; opacity:0; transform:translateY(14px);
            animation:sp-rise .6s .65s cubic-bezier(.2,.7,.2,1) forwards; }
          .st-key-login_card [data-testid="stForm"] { border:none; padding:0; }
          .st-key-login_card label p, .st-key-login_card [data-testid="stCheckbox"] p { color:#fff; }
          .st-key-login_card [data-testid="stCheckbox"] label > div:not([data-testid]) {
            border:1.5px solid rgba(255,255,255,.8) !important; background:transparent !important; }
          .st-key-login_card [data-testid="stCheckbox"] label[data-selected="true"] > div:not([data-testid]) {
            background:#fff !important; border-color:#fff !important; }
          .st-key-login_card [data-testid="stCheckbox"] svg polyline { stroke:var(--brand) !important; }
          .st-key-login_card [data-testid="stTextInputRootElement"] { background:#fff; border:none;
            border-radius:4px; }
          .st-key-login_card [data-testid="stTextInputRootElement"]:focus-within {
            box-shadow:0 0 0 3px rgba(255,255,255,.35); }
          .st-key-login_card button[kind^="primary"], .st-key-login_card button[kind^="secondary"] {
            background:#fff !important; color:var(--brand) !important; border:none !important;
            min-height:44px; font-weight:800; }
          .st-key-login_card div[data-testid] button, .st-key-login_card div[data-testid] button > div {
            justify-content:center; width:100%; }
          .st-key-login_card div[data-testid] button p { color:var(--brand) !important; font-weight:800 !important;
            font-size:.95rem !important; }
          .st-key-login_card button:hover { background:#EDE7F6 !important; }
          .st-key-login_card [data-testid="stCaptionContainer"], .st-key-login_card [data-testid="stCaptionContainer"] p {
            color:rgba(255,255,255,.7) !important; }
          @media (max-width: 700px) {
            .sp-hero { margin:0 -10px 18px; }
            .sp-top { padding:8px 14px; } .sp-top span { display:none; }
            .sp-title { padding:8vh 14px 0; } .sp-sub { padding:14px 14px 0; font-size:.95rem; }
            .st-key-login_card { margin:0; max-width:none; } }
          @media (prefers-reduced-motion: reduce) {
            .sp-title span, .sp-sub, .st-key-login_card { animation:none; opacity:1; transform:none; } }

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
          .tp { display:flex; flex-direction:column; gap:0; margin-top:0; }
          .tp-row { display:grid; grid-template-columns:118px 46px 1fr 46px; align-items:center; gap:8px;
            line-height:1.25; min-height:21px; }
          .tp-f, .tp-o { font-weight:800; font-size:.85rem; color:var(--ink); }
          .tp-head .tp-f, .tp-head .tp-o { font-size:.75rem; font-weight:700; color:var(--muted); }
          .tp-head { min-height:16px; }
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
          .wa-rot { display:grid; }
          .wa-rot-item { grid-area:1 / 1; opacity:0; }
          .wa-rot:hover .wa-rot-item { animation-play-state:paused; }
          .pl-photo { width:42px; height:42px; border-radius:50%; flex:none; object-fit:cover;
            object-position:top; background:#fff; border:2px solid rgba(255,255,255,.85); }
          /* In a comparison: a thick ring in the player's chart colour, a thin white
             edge so the purple ring still shows on the purple band; B overlaps A. */
          .pl-photo.ring { border-width:3px; border-style:solid; box-shadow:0 0 0 1.5px #fff; }
          .pl-photo.ring + .pl-photo.ring { margin-left:-16px; }
          .pl-initials { display:flex; align-items:center; justify-content:center; background:var(--brand-2);
            color:#fff; font-weight:800; font-size:.95rem; letter-spacing:.5px; }
          .cv-band.player { gap:clamp(9px, 1vw, 18px); }
          .cmp-name { display:inline-flex; align-items:center; gap:5px; }
          .cmp-v { margin:0 8px; font-weight:500; opacity:.75; }
          .cmp-name i { width:10px; height:10px; border-radius:50%; display:inline-block;
            box-shadow:0 0 0 1.5px #fff; }
          .cmp-line { display:flex; align-items:baseline; gap:5px; font-size:.8rem; color:var(--muted);
            line-height:1.35; }
          .cmp-line i { width:8px; height:8px; border-radius:50%; flex:none; align-self:center; }
          .cmp-line .nm { flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis;
            white-space:nowrap; }
          .cmp-line b { font-size:1rem; font-weight:600; color:var(--ink); }
          .cmp-line.lead b { font-weight:800; }
          .cmp-rk { font-size:.7rem; font-weight:700; color:var(--brand); }
          .cmp-bar { display:flex; height:5px; border-radius:3px; overflow:hidden; gap:2px; margin-top:4px; }
          .cmp-wrap { overflow-y:auto; }
          [data-testid="stChatMessage"] { padding:6px 4px; }
          [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li { font-size:.84rem; }

          div[data-testid="stButton"] button { min-height:30px; border-radius:8px; padding:4px 10px;
            justify-content:flex-start; text-align:left; background:#fff; border:1px solid var(--line); }
          div[data-testid="stButton"] button:hover { border-color:var(--brand); color:var(--brand); }
          div[data-testid="stButton"] button p { font-size:.78rem; font-weight:500; text-align:left; }
          div[data-testid="stButton"] button > div { justify-content:flex-start; width:100%; }
          div[data-testid="stButton"] button[kind="tertiary"] { border:none; background:transparent; }
          .st-key-tour_btn button, .st-key-signout_btn button, .st-key-usage_btn button { width:34px; height:34px; min-height:34px;
            padding:0; border-radius:50%; justify-content:center; border:1.5px solid var(--brand);
            color:var(--brand); }
          .st-key-signout_btn button:hover, .st-key-usage_btn button:hover { background:var(--brand); color:#fff; }
          .st-key-tour_btn button p { font-size:1rem; font-weight:800; text-align:center; }
          .st-key-tour_btn button:hover { background:var(--brand); color:#fff; }
          div[data-testid="stButton"] button[kind="primary"] { background:var(--brand); border-color:var(--brand); color:#fff; }
          .wa-sub { font-size:.75rem; font-weight:700; color:var(--muted); margin:6px 0 2px; }
          .wa-wait { font-size:.8rem; font-weight:600; color:var(--brand); margin:2px 0 4px; }
          .wa-wait .wa-doing { color:var(--muted); font-weight:500; }
          /* Spinning footy: fixed size, so the line doesn't shift as it turns. */
          .wa-ball { display:inline-block; width:1.15em; height:1.15em; vertical-align:-.25em;
            margin-right:2px; animation:wa-spin 1.1s linear infinite; }
          @keyframes wa-spin { to { transform:rotate(360deg); } }
          @media (prefers-reduced-motion: reduce) { .wa-ball { animation:none; } }
          /* Seconds since the question was asked, counted by the browser. A
             negative animation-delay carries the count on when the line is redrawn. */
          @property --wa-s { syntax:'<integer>'; initial-value:0; inherits:false; }
          .wa-secs { color:var(--muted); font-weight:500; font-variant-numeric:tabular-nums;
            counter-reset:wa-s var(--wa-s); animation:wa-count 600s steps(600, end) forwards; }
          .wa-secs::after { content:counter(wa-s) " s"; }
          @keyframes wa-count { from { --wa-s:0; } to { --wa-s:600; } }
          .wa-flag { font-size:.75rem; color:#8A5A00; background:#FFF6E0; border-radius:6px;
            padding:4px 8px; margin:4px 0; }
          .wa-earlier { border-top:1px solid var(--line); padding-top:8px; margin-top:10px; }
          .st-key-wa_history div[data-testid="stElementContainer"]:has(iframe[height="0"]) {
            position:absolute; width:0; height:0; overflow:hidden; margin:0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_side_panel_css():
    """Wharf-ai down the side (desktop, split): the panel is a fixed height, its
    header and question box stay put and only the chat scrolls, taking whatever
    height the header leaves (it wraps on narrow windows)."""
    st.markdown("""
        <style>
          .st-key-card_wharfai { overflow:hidden !important; }
          .st-key-card_wharfai > [data-testid="stLayoutWrapper"] { flex:1 1 0; min-height:0; }
          .st-key-card_wharfai > [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {
            height:100%; flex-wrap:nowrap; }
          [data-testid="stLayoutWrapper"]:has(> .st-key-wa_history) { flex:1 1 0; min-height:0; }
          .st-key-wa_history { height:100% !important; max-height:none !important; }
        </style>
    """, unsafe_allow_html=True)


def inject_phone_css():
    """Extra rules for the phone layout (app.PHONE): one scrolling column,
    touch-sized targets, text that wraps instead of being cut off."""
    st.markdown(
        """
        <style>
          .block-container { padding:0 10px 32px !important; }
          [data-testid="stLayoutWrapper"]:has(> .st-key-topbar) { margin:0 -10px 4px; }
          .mc-div { display:none; }   /* the match band wraps onto lines here */
          .tk-strip { margin:2px -10px 0; }
          .st-key-topbar { padding:6px 10px; }
          /* Streamlit stacks columns below 640px; the controls row stays one line. */
          .st-key-topbar div[data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important; gap:6px; }
          .st-key-topbar div[data-testid="stColumn"] { min-width:0 !important; width:auto !important; }
          /* The season buttons (one per season) get the room they need; the view dropdown the rest. */
          .st-key-topbar div[data-testid="stColumn"]:nth-child(1) { flex:0 0 auto !important; }
          .st-key-topbar div[data-testid="stColumn"]:nth-child(2) { flex:1 1 0 !important; }
          .st-key-season div[data-testid="stButtonGroup"] button { padding:4px 8px; }
          .st-key-topbar div[data-testid="stColumn"]:nth-child(n+3) { flex:0 0 40px !important; }
          .st-key-tour_btn button, .st-key-signout_btn button, .st-key-usage_btn button { width:40px; height:40px; min-height:40px; }
          div[data-testid="stButtonGroup"] button { min-height:40px; padding:4px 10px; }
          div[data-testid="stButtonGroup"] button p { font-size:.85rem; }
          div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { min-height:40px; font-size:.9rem; }
          div[data-testid="stButton"] button { min-height:44px; }
          div[data-testid="stButton"] button p { font-size:.88rem; }
          div[data-testid="stButton"] button[kind="tertiary"] { min-height:36px; }

          /* Bands wrap onto a second line instead of cutting the title off. */
          .cv-band { height:auto; min-height:52px; flex-wrap:wrap; row-gap:6px; column-gap:14px;
            padding:9px 12px; }
          .cv-band .ttl { flex:1 1 100%; }
          .cv-band.player .ttl { flex:1 1 0; }  /* the initials or photo sit beside the name */
          .cv-band .ttl small { white-space:normal; }

          /* Tiles two to a row */
          .cv-tiles { grid-template-columns:repeat(2, minmax(0, 1fr)) !important; }
          .cv-tile .val { font-size:1.3rem; }

          /* Card text wraps; there is room to scroll */
          .card-title, .card-take, .card-title .take { white-space:normal; }
          .card-title .key { display:inline-block; margin-left:8px; }
          div[class*="st-key-card_"] { padding:10px 12px; }
          .tp-row { grid-template-columns:88px 50px 1fr 50px; gap:6px; }
          /* Player vs player table: season averages and the gap only */
          .cmp-wrap th:nth-child(3), .cmp-wrap td:nth-child(3),
          .cmp-wrap th:nth-child(5), .cmp-wrap td:nth-child(5) { display:none; }
          .tp-f, .tp-o { font-size:.8rem; }
          .st-key-jump_dash { display:flex; justify-content:flex-end; }
          .st-key-jump_dash button p { font-weight:700; color:var(--brand); }
          div[data-testid="stElementContainer"]:has(iframe[height="0"]) {
            position:absolute; width:0; height:0; overflow:hidden; margin:0; }
          .st-key-m_more { margin-top:6px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_tablet_css(mode):
    """Extra rules for the tablet layouts (layout.mode "stack" and "split"): the
    page scrolls, cards sit two to a row, tiles three to a row, card text
    wraps, and in "split" Wharf-ai stays in view while the dashboard scrolls."""
    sticky = """
          div[data-testid="stColumn"]:has(.st-key-card_wharfai) {
            position:sticky; top:8px; align-self:flex-start; }""" if mode == "split" else ""
    st.markdown(
        f"""
        <style>
          .block-container {{ padding:0 14px 32px !important; }}
          .cv-tiles {{ grid-template-columns:repeat(3, minmax(0, 1fr)) !important; }}
          .card-title, .card-take, .card-title .take {{ white-space:normal; }}
          .cv-band .opt {{ display:none; }}
          div[data-testid="stButton"] button {{ min-height:38px; }}
          div[data-testid="stButtonGroup"] button {{ min-height:36px; }}
          div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{ min-height:36px; }}
          .st-key-tour_btn button, .st-key-signout_btn button, .st-key-usage_btn button {{ width:38px; height:38px; min-height:38px; }}
          .st-key-jump_dash {{ display:flex; justify-content:flex-end; }}
          .st-key-jump_dash button p {{ font-weight:700; color:var(--brand); }}
          div[data-testid="stElementContainer"]:has(iframe[height="0"]) {{
            position:absolute; width:0; height:0; overflow:hidden; margin:0; }}{sticky}
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


# A red AFL ball with white laces (inline, so it can spin; the 🏉 emoji is a
# brown rugby ball on most systems and can't be recoloured).
BALL_SVG = ('<svg class="wa-ball" viewBox="0 0 24 24" aria-hidden="true">'
             '<ellipse cx="12" cy="12" rx="10.5" ry="6.5" fill="#C8102E"/>'
             '<path d="M4 12h16" stroke="#fff" stroke-width="1.1" stroke-linecap="round"/>'
             '<path d="M9 10.3v3.4M11 10.3v3.4M13 10.3v3.4M15 10.3v3.4" stroke="#fff" '
             'stroke-width="1.1" stroke-linecap="round"/></svg>')


def login_hero():
    """The sign-in screen, after the club site's home page: the whole page in
    the club purple, a thin strip, the headline in the serif with "Freo" in
    italic (our own line, not the club's slogan; the words rise in), and one
    line on what's inside. The sign-in sits under it (auth._splash). No club
    marks, sponsor logos or photos, and no data before sign-in."""
    words = "The numbers behind".split()
    title = "".join(f'<span style="animation-delay:{0.08 + 0.09 * i:.2f}s">{w}</span> '
                    for i, w in enumerate(words))
    title += f'<span style="animation-delay:{0.08 + 0.09 * len(words):.2f}s"><i>Freo</i></span>'
    st.markdown(
        f'<div class="sp-hero"><div class="sp-top"><b>Coach View</b>'
        f'<span>Fremantle Dockers · performance analysis</span></div>'
        f'<div class="sp-title">{title}</div>'
        f'<div class="sp-sub">Every game, every player and every club, '
        f'powered by Wharf-ai</div></div>',
        unsafe_allow_html=True)


def brand_title():
    """The bar's title, set like the club site's headline: a serif, one word in italic."""
    st.markdown('<div class="cv-brand"><i>Freo</i> Coach View</div>', unsafe_allow_html=True)


def demo_band(season, game_label, player):
    """The demo view's band: says plainly that what's below is simulated."""
    what = (player if player != "Whole team" else "The team") + " · " + (
        f"{season} season" if game_label == "Whole season" else game_label)
    st.markdown(
        f'<div class="cv-band demo"><div class="ttl">{html.escape(what)}'
        f'<small>Real counts from the box score; positions and GPS running are simulated</small></div>'
        f'<div class="cv-stat"><b><i class="cv-res demo-pill">Demo · simulated</i></b>'
        f'<span>Not real tracking data</span></div></div>', unsafe_allow_html=True)


def header_band(season, rec, form, data_note, last=None):
    """form: list of (result, tooltip) for the last five games. last: the latest
    game (a team row), shown as a small match-card score on wide windows."""
    chips = "".join(
        f'<i title="{html.escape(t)}" style="background:'
        f'{result_colour(r)}">{r}</i>'
        for r, t in form)
    stats = [
        (record_text(rec["wins"], rec["losses"], rec.get("draws", 0)), "Record"),  # the lead number
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
        f'<div class="cv-stat" title="Last 5 results"><div class="cv-form">{chips}</div></div>'
        f'{_last_match(last)}</div>',
        unsafe_allow_html=True,
    )


def _last_match(g):
    """'Last match · GF v BRL · 89 v 96 · L', at the end of the season band."""
    if g is None:
        return ""
    from data import abbr
    return (f'<i class="mc-div opt2"></i><div class="cv-stat mc-last opt2">'
            f'<b>{g["freo_score"]} <em>v</em> {g["opp_score"]} '
            f'<i class="cv-res" style="background:{result_colour(g["result"])}">{g["result"]}</i></b>'
            f'<span>Last match · {html.escape(g["round"])} v {html.escape(abbr(g["opponent"]))}</span></div>')


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


def leaders_pair(freo, opp, opp_label, opp_color):
    """Match leaders for both sides: a row per role, Freo's leader and the
    opposition's (surnames, to fit), each with their number."""
    def cell(r, colour):
        name = r["player"].split()[-1] if r["player"] != "-" else "-"
        return (f'<span class="lp-n" title="{html.escape(r["player"])}">{html.escape(name)}</span>'
                f'<span class="lp-v" style="color:{colour}">{html.escape(r["value"])}</span>')
    rows = (f'<div class="lp-row lp-head"><span></span><span class="lp-side">Freo</span>'
            f'<span class="lp-side" style="color:{opp_color}">{html.escape(opp_label)}</span></div>')
    for f, o in zip(freo, opp):
        rows += (f'<div class="lp-row"><span class="lp-role">{html.escape(f["role"])}</span>'
                 f'<span class="lp-cell">{cell(f, COLORS["freo"])}</span>'
                 f'<span class="lp-cell">{cell(o, opp_color)}</span></div>')
    st.markdown(f'<div class="lp">{rows}</div>', unsafe_allow_html=True)


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


def ticker(parts, cls="", speed=45):
    """A news-style ticker: the parts (HTML) scroll right to left in a loop, in
    the browser (CSS only, no reruns), pausing on hover. The parts are drawn
    twice so the loop is seamless; the second copy is hidden from screen readers.
    speed: roughly pixels a second, from the text length."""
    if not parts:
        return
    items = "".join(f'<span class="tk-item">{p}</span>' for p in parts)
    chars = sum(len(re.sub(r"<[^>]+>", "", p)) for p in parts)
    secs = max(20, int((chars * 7 + 60 * len(parts)) / speed))
    st.markdown(
        f'<div class="tk {cls}"><div class="tk-track" style="animation-duration:{secs}s">'
        f'<div>{items}</div><div aria-hidden="true">{items}</div></div></div>',
        unsafe_allow_html=True)


LOGIN_TICKER = [
    "Every Freo game, quarter by quarter", "Player form against their own season average",
    "Scout any club against the league", "Compare two players side by side",
    "A quarter-time check for game day", "Ask Wharf-ai anything about the numbers",
    "Every number calculated from the data, never guessed",
]


def login_ticker():
    """The sign-in screen's ticker along the bottom: what's inside, no numbers."""
    ticker([html.escape(t) for t in LOGIN_TICKER], cls="tk-login", speed=40)


def insight_ticker(texts, cls="tk-bar"):
    """The season's insights as a ticker in the top bar."""
    ticker([_md_bold(t) for t in texts], cls=cls)


def insight_card(text):
    st.markdown(f'<div class="wa-insight"><div class="tag">Insight</div>{_md_bold(text)}</div>',
                unsafe_allow_html=True)


def match_band(game, venue_date):
    """Header band for match mode: result, score line and margin."""
    margin = abs(int(game["margin"]))
    res = {"W": f"Won by {margin}", "L": f"Lost by {margin}"}.get(game["result"], "Drew")
    color = result_colour(game["result"])
    fq, oq = game["freo_qtrs"].split()[-1], game["opp_qtrs"].split()[-1]
    # Laid out like the club site's match card: the score big in the middle,
    # goals.behinds under each side, the result pill, thin white dividers. Freo
    # purple fades into the opposition's dark club colour, their second colour
    # as a stripe on the right.
    club = club_colours(game["opponent"])
    style = (f'background:linear-gradient(100deg, var(--brand) 0%, var(--brand-2) 40%, '
             f'{club["band"]} 100%); border-right:6px solid {club["accent"]}; '
             f'--mark:{marks.uri(game["opponent"])}')
    st.markdown(
        f'<div class="cv-band match mc" style="{style}"><div class="ttl">{html.escape(game["round"])} v '
        f'{html.escape(game["opponent"])}<small>{html.escape(venue_date)}</small></div>'
        f'<i class="mc-div"></i>'
        f'<div class="mc-score"><div class="mc-team"><b>Fremantle</b><span>{fq}</span></div>'
        f'<b class="mc-num">{game["freo_score"]}</b><em>v</em><b class="mc-num">{game["opp_score"]}</b>'
        f'<div class="mc-team r"><b>{html.escape(game["opponent"])}</b><span>{oq}</span></div></div>'
        f'<i class="mc-div"></i>'
        f'<div class="cv-stat mc-res"><b><i class="cv-res" style="background:{color}">{res}</i></b>'
        f'<span>{html.escape(game["type"])}</span></div></div>',
        unsafe_allow_html=True)


def tape(rows, opp_color=None, names=None):
    """Tale of the tape: one split bar per stat, Freo share (purple) against the
    opposition (in their club's chart colour), numbers either side, and a tick
    at Freo's season average share."""
    bar = f' style="background:{opp_color}"' if opp_color else ""
    out = ""
    if names:   # the two sides named over their number columns, in place of a colour key
        out += (f'<div class="tp-row tp-head"><span></span><span class="tp-f">{html.escape(names[0])}</span>'
                f'<span></span><span class="tp-o">{html.escape(names[1])}</span></div>')
    for r in rows:
        f = f'{r["freo"]:,.0f}'
        o = f'{r["opp"]:,.0f}'
        tip = (f'{r["stat"]}: Freo {f}, opp {o}. Season average share '
               f'{r["season_share"]:.0f}% (diff {r["season_diff"]:+.1f} a game)')
        out += (f'<div class="tp-row" title="{html.escape(tip)}">'
                f'<span class="tp-lbl">{html.escape(r["stat"])}</span><span class="tp-f">{f}</span>'
                f'<div class="tp-bar"{bar}><i style="width:{r["share"]:.1f}%"></i>'
                f'<em style="left:{r["season_share"]:.1f}%"></em></div>'
                f'<span class="tp-o">{o}</span></div>')
    st.markdown(f'<div class="tp">{out}</div>', unsafe_allow_html=True)


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def scout_band(team, season, lad_row, last5):
    """Header band for the scout report: record, ladder spot, percentage, form."""
    chips = "".join(
        f'<i title="{html.escape(t)}" style="background:'
        f'{result_colour(r)}">{r}</i>' for r, t in last5)
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
        f'border-left:6px solid {club["accent"]};--mark:{marks.uri(team)}"><div class="ttl">Scout: {html.escape(team)}'
        f'<small>{season} · percentage {lad_row["pct"]:.1f} (home and away)</small></div>{stat_html}'
        f'<div class="cv-stat" title="Last 5 results"><div class="cv-form">{chips}</div></div></div>',
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


def opponents_table(grid, seasons, max_h=None):
    """Every game against each club, a column per season: a chip per game with
    round and margin (hover for the score and venue), then record and average margin."""
    def chip(g):
        tip = (f"{g['season']} {g['round']} ({g['type']}) at {g['venue']}: "
               f"Freo {g['freo_score']} to {g['opp_score']}")
        return (f'<span class="op-chip" style="background:{result_colour(g["result"])}" '
                f'title="{html.escape(tip)}">{g["round"]} {g["margin"]:+d}</span>')
    head = "".join(f"<th>{s}</th>" for s in seasons)
    rows = ""
    for r in grid:
        cells = "".join("<td>" + "".join(chip(g) for g in r["games"].get(s, [])) + "</td>"
                        for s in seasons)
        rows += (f'<tr><td class="op-name">{html.escape(r["opponent"])}</td>{cells}'
                 f'<td class="op-num">{record_text(r["wins"], r["losses"], r["draws"])}</td>'
                 f'<td class="op-num">{r["avg_margin"]:+.1f}</td></tr>')
    style = f' style="max-height:{int(max_h)}px"' if max_h else ""
    st.markdown(
        f'<div class="op-wrap"{style}><table class="op-grid"><thead><tr><th>Opponent</th>{head}'
        f'<th>Record</th><th>Avg margin</th></tr></thead><tbody>{rows}</tbody></table></div>',
        unsafe_allow_html=True)


def h2h_table(rows):
    """Freo's games against one club: result chip, score and two key counts."""
    body = ""
    for r in rows.itertuples():
        color = result_colour(r.result)
        body += (f'<tr><td>{r.season} {html.escape(r.round)}</td><td>{html.escape(r.venue)}</td>'
                 f'<td><span class="op-chip" style="background:{color}">{r.result} '
                 f'{int(r.margin):+d}</span></td><td class="op-num">{r.freo_score}-{r.opp_score}</td>'
                 f'<td>{int(r.freo_inside_50s - r.opp_inside_50s):+d}</td>'
                 f'<td>{int(r.freo_contested_poss - r.opp_contested_poss):+d}</td></tr>')
    st.markdown('<table class="op-grid"><thead><tr><th>Game</th><th>Venue</th><th>Result</th>'
                '<th>Score</th><th>I50 diff</th><th>CP diff</th></tr></thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)


def _avatar(player, photo_url=None, ring=None):
    """A round headshot, or the player's initials in the club purple. ring: a
    colour for the border (the player's chart colour in a comparison)."""
    style = f' style="border-color:{ring};{"background:" + ring if not photo_url else ""}"' if ring else ""
    cls = " ring" if ring else ""
    if photo_url:
        return f'<img class="pl-photo{cls}" src="{html.escape(photo_url)}" alt=""{style} loading="lazy">'
    return f'<span class="pl-photo pl-initials{cls}"{style}>{_initials(player)}</span>'


def _initials(player):
    parts = [p for p in str(player).replace("'", "").split() if p]
    return html.escape("".join(p[0] for p in parts[:2]).upper())


def player_band(player, season, me, details=None, photo_url=None,
                hero_label="Disposals", hero_col="disposals"):
    """Header band for a player: photo or initials, name, number, position, age,
    height, and their best squad ranking this season as the lead number (games
    and goals on wider screens)."""
    details = details or {}
    games = len(me)
    goals = int(me["goals"].sum()) if "goals" in me else 0
    jumper = int(me["jumper"].iloc[-1]) if games and "jumper" in me else None
    # The lead number is the player's best squad ranking; averages are in the tiles below.
    stats = [(str(games), "Games", "opt"), (str(goals), "Goals", "opt")]
    top = details.get("top")
    if top:
        stats.insert(0, (_ordinal(top["rank"]), f"{top['stat']} in squad", "hero"))
    else:
        stats.insert(0, (f"{me[hero_col].mean():.1f}" if games else "-", f"{hero_label} a game", "hero"))
    stat_html = "".join(f'<div class="cv-stat {cls}"><b>{v}</b><span>{html.escape(l)}</span></div>'
                        for v, l, cls in stats)
    bits = [f"#{jumper}" if jumper else None, details.get("position"),
            f"{details['age']} yrs" if details.get("age") else None,
            f"{details['height_cm']} cm" if details.get("height_cm") else None]
    sub_line = " · ".join(b for b in bits if b) or f"{season} season"
    st.markdown(f'<div class="cv-band player">{_avatar(player, photo_url)}<div class="ttl">'
                f'{html.escape(player)}<small>{html.escape(sub_line)}</small></div>{stat_html}</div>',
                unsafe_allow_html=True)


def insight_rotator(texts, start=0, seconds=30):
    """Insight card that fades to the next insight every `seconds`, in the
    browser (no reruns, so it can't interrupt a streaming answer). Pauses on
    hover. All insights share one grid cell, so the card is as tall as the
    longest and doesn't jump."""
    texts = texts[start:] + texts[:start]
    n = len(texts)
    if n == 0:
        return
    if n == 1:
        insight_card(texts[0])
        return
    cycle = n * seconds
    show = 100 / n
    fade = min(1.5, show / 6)
    items = "".join(
        f'<div class="wa-rot-item" style="animation-delay:-{((n - i) % n) * seconds}s">'
        f'<div class="tag">Insight {i + 1} of {n}</div>{_md_bold(t)}</div>'
        for i, t in enumerate(texts))
    st.markdown(
        f'<style>@keyframes wa-rot-{n} {{ 0% {{opacity:0; visibility:visible}} '
        f'{fade:.2f}% {{opacity:1}} {show - fade:.2f}% {{opacity:1}} '
        f'{show:.2f}% {{opacity:0; visibility:hidden}} 100% {{opacity:0; visibility:hidden}} }}'
        f'.wa-rot-item {{ animation: wa-rot-{n} {cycle}s linear infinite; }}</style>'
        f'<div class="wa-insight wa-rot">{items}</div>', unsafe_allow_html=True)


# ---- Player vs player --------------------------------------------------------
PAIR = (COLORS["freo"], COLORS["opp"])   # player A, player B (charts.PAIR)


def compare_band(a, b, season, together, photos=(None, None)):
    """Header band for two players: each one's photo (or initials) ringed in
    their chart colour, both names, and how many games they played together,
    with Freo's record in them."""
    keys = '<span class="cmp-v">v</span>'.join(
        f'<span class="cmp-name">{html.escape(n.split()[-1])}</span>' for n in (a, b))
    rec = record_text(together["wins"], together["losses"], together.get("draws", 0))
    st.markdown(
        f'<div class="cv-band player cmp">{_avatar(a, photos[0], ring=PAIR[0])}'
        f'{_avatar(b, photos[1], ring=PAIR[1])}<div class="ttl">{keys}'
        f'<small>{season} · {together["games"]} games together, {rec}</small></div>'
        f'<div class="cv-stat opt"><b>{together["games_a"]} / {together["games_b"]}</b>'
        f'<span>Games each</span></div></div>',
        unsafe_allow_html=True)


def compare_tiles_row(cmp, names, labels):
    """One tile per stat: each player's per game average and squad rank, the
    leader in bold, and a bar showing their share of the two averages."""
    cells = []
    for _, r in cmp[cmp["stat"].isin(labels)].iterrows():
        va, vb = r["avg_a"], r["avg_b"]
        lines = ""
        for key, n, c, v in (("a", names[0], PAIR[0], va), ("b", names[1], PAIR[1], vb)):
            lead = v is not None and v == v and v >= max(x for x in (va, vb) if x == x)
            rk = r[f"rank_{key}"]
            rk_html = f' <span class="cmp-rk">{_ordinal(int(rk))}</span>' if rk == rk and rk else ""
            val = f"{v:.1f}" if v == v and v is not None else "-"
            lines += (f'<div class="cmp-line{" lead" if lead else ""}"><i style="background:{c}"></i>'
                      f'<span class="nm">{html.escape(n.split()[-1])}</span><b>{val}</b>{rk_html}</div>')
        tot = (va or 0) + (vb or 0)
        share = (va or 0) / tot * 100 if tot else 50
        bar = (f'<div class="cmp-bar"><span style="width:{share:.0f}%;background:{PAIR[0]}"></span>'
               f'<span style="width:{100 - share:.0f}%;background:{PAIR[1]}"></span></div>')
        cells.append(f'<div class="cv-tile"><div class="lbl">{html.escape(r["stat"])} a game</div>'
                     f'{lines}{bar}</div>')
    st.markdown(f'<div class="cv-tiles" style="--n:{len(cells)}">{"".join(cells)}</div>',
                unsafe_allow_html=True)


def compare_table(cmp, names, last_n=5):
    """Every profile stat: each player's season and last-games average, and the gap."""
    a, b = (n.split()[-1] for n in names)
    body = ""
    for _, r in cmp.iterrows():
        if max(abs(r["avg_a"] or 0), abs(r["avg_b"] or 0)) < 0.05:
            continue                        # e.g. hitouts for two midfielders
        gap = (r["avg_a"] or 0) - (r["avg_b"] or 0)
        if abs(gap) < 0.05:
            gap = 0
        who = a if gap > 0 else b if gap < 0 else "level"
        ca, cb = ("op-num" if gap > 0 else ""), ("op-num" if gap < 0 else "")   # the leader in bold
        body += (f'<tr><td class="op-name">{html.escape(r["stat"])}</td>'
                 f'<td class="{ca}">{r["avg_a"]:.1f}</td><td>{r["last_a"]:.1f}</td>'
                 f'<td class="{cb}">{r["avg_b"]:.1f}</td><td>{r["last_b"]:.1f}</td>'
                 f'<td>{f"{abs(gap):.1f} {html.escape(who)}" if gap else "level"}</td></tr>')
    st.markdown(f'<div class="cmp-wrap"><table class="op-grid"><thead><tr><th>Per game</th>'
                f'<th>{html.escape(a)}</th><th>last {last_n}</th><th>{html.escape(b)}</th>'
                f'<th>last {last_n}</th><th>Gap</th></tr></thead><tbody>{body}</tbody></table></div>',
                unsafe_allow_html=True)
