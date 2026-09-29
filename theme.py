"""Colours, Plotly styling, CSS and card components for the dashboard.

Purple and white theme with a card-grid layout: a deep-purple left nav rail, a
grey canvas, and white cards with small caps section titles, mirroring a
performance-analysis dashboard. The categorical palette was validated for the
lightness band, chroma floor, colour-vision separation and contrast on a light
surface. Colour follows the entity (Freo is always purple), never rank.
"""

import streamlit as st

COLORS = {
    "freo": "#7C3AED",     # Fremantle (categorical slot 1)
    "opp": "#C25E12",      # Opposition (categorical slot 2)
    "teal": "#0D9488",     # third series / secondary accent
    "magenta": "#BE185D",  # fourth series
    "win": "#15803D",
    "loss": "#DC2626",
    "ink": "#1F2937",
    "muted": "#6B7280",
    "grid": "#E7E3EF",
    "brand": "#2A0A4A",    # deep Freo purple (nav rail, top band, hero numbers)
    "brand2": "#4C1D95",
    "freo_fill": "rgba(124,58,237,0.16)",
    "opp_fill": "rgba(194,94,18,0.14)",
}

PALETTE = [COLORS["freo"], COLORS["opp"], COLORS["teal"], COLORS["magenta"]]
FONT = "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"


def style_fig(fig, y_title="", unified=True, height=380):
    """Shared chart look: white surface, recessive grid and axes, a legend across
    the top, a single y axis (never dual-axis)."""
    fig.update_layout(
        template="plotly_white",
        font=dict(family=FONT, color=COLORS["ink"], size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=12, t=30, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=COLORS["muted"], size=12)),
        hovermode="x unified" if unified else "closest",
        height=height,
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(color=COLORS["muted"]),
                     linecolor=COLORS["grid"])
    fig.update_yaxes(title=dict(text=y_title, font=dict(color=COLORS["muted"], size=12)),
                     gridcolor=COLORS["grid"], zeroline=False,
                     tickfont=dict(color=COLORS["muted"]))
    return fig


def inject_css():
    st.markdown(
        """
        <style>
          .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1300px; }

          /* Top band */
          .freo-band {
            background: linear-gradient(100deg, #2A0A4A 0%, #4C1D95 55%, #6D28D9 100%);
            color:#fff; padding:16px 22px; border-radius:14px; margin-bottom:16px;
            display:flex; justify-content:space-between; align-items:center;
          }
          .freo-band h1 { color:#fff; font-size:1.5rem; margin:0; font-weight:700; letter-spacing:.2px; }
          .freo-band p { color:#E9D5FF; margin:.25rem 0 0; font-size:.88rem; }
          .band-chip { text-align:right; line-height:1.1; }
          .band-chip span { display:block; color:#C4B5FD; font-size:.66rem; letter-spacing:.14em; }
          .band-chip b { color:#fff; font-size:1.35rem; }

          /* Dark purple nav rail */
          section[data-testid="stSidebar"] { background:#2A0A4A; }
          section[data-testid="stSidebar"] h1,
          section[data-testid="stSidebar"] h2,
          section[data-testid="stSidebar"] h3,
          section[data-testid="stSidebar"] p,
          section[data-testid="stSidebar"] label,
          section[data-testid="stSidebar"] span,
          section[data-testid="stSidebar"] div { color:#EDE9FE; }
          section[data-testid="stSidebar"] hr { border-color:#4C1D95; }

          /* Cards (any bordered container) */
          div[data-testid="stVerticalBlockBorderWrapper"] {
            background:#FFFFFF; border:1px solid #E7E3EF; border-radius:14px;
            padding:8px 16px 14px; box-shadow:0 1px 3px rgba(42,10,74,.07);
          }
          .card-title {
            text-transform:uppercase; letter-spacing:.07em; font-size:.72rem;
            font-weight:700; color:#7C3AED; border-bottom:1px solid #F0EDF7;
            padding-bottom:7px; margin:2px 0 12px;
          }

          h2, h3 { color:#2A0A4A; }

          /* Hero number */
          .hero-num { font-size:2.6rem; font-weight:800; color:#2A0A4A; line-height:1; }
          .hero-label { color:#6B7280; font-size:.82rem; margin-top:3px; }

          /* Leader list */
          .lead-row { display:flex; justify-content:space-between; align-items:baseline;
            padding:8px 0; border-bottom:1px solid #F3F0F9; }
          .lead-row:last-child { border-bottom:none; }
          .lead-role { color:#9333EA; font-size:.66rem; text-transform:uppercase; letter-spacing:.05em; }
          .lead-name { font-weight:600; color:#1F2937; font-size:.95rem; }
          .lead-val { font-weight:800; color:#7C3AED; font-size:1.1rem; }
          .lead-val small { color:#9CA3AF; font-weight:600; font-size:.7rem; }

          /* Insight callout */
          .insight-box { background:linear-gradient(135deg,#7C3AED 0%, #4C1D95 100%);
            color:#fff; border-radius:12px; padding:14px 16px; height:100%; }
          .insight-box .big { font-size:1.7rem; font-weight:800; line-height:1; }
          .insight-box .txt { font-size:.84rem; color:#EDE9FE; margin-top:8px; }

          /* Results strip */
          .results-strip { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 4px; }
          .chip { border-radius:8px; padding:6px 9px; min-width:74px; text-align:center;
            font-size:.72rem; line-height:1.25; color:#fff; }
          .chip .rnd { font-weight:700; font-size:.7rem; opacity:.92; }
          .chip .opp { display:block; font-weight:600; }
          .chip .mgn { display:block; opacity:.95; }

          /* Inline insight (light) used on analysis pages */
          .insight { background:#F5F1FB; border-left:4px solid #7C3AED; border-radius:8px;
            padding:12px 14px; margin:4px 0 10px; color:#1F2937; font-size:.92rem; }
          .insight b { color:#4C1D95; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def band(title, subtitle, season=None):
    chip = (f'<div class="band-chip"><span>SEASON</span><b>{season}</b></div>'
            if season is not None else "")
    st.markdown(
        f'<div class="freo-band"><div><h1>{title}</h1><p>{subtitle}</p></div>{chip}</div>',
        unsafe_allow_html=True,
    )


# ---- card components -------------------------------------------------------
def card_title(text):
    st.markdown(f'<div class="card-title">{text}</div>', unsafe_allow_html=True)


def hero(number, label):
    st.markdown(f'<div class="hero-num">{number}</div><div class="hero-label">{label}</div>',
                unsafe_allow_html=True)


def leader_list(items):
    """items: list of (role, name, value_html)."""
    rows = ""
    for role, name, val in items:
        rows += (f'<div class="lead-row"><div>'
                 f'<div class="lead-role">{role}</div>'
                 f'<div class="lead-name">{name}</div></div>'
                 f'<div class="lead-val">{val}</div></div>')
    st.markdown(rows, unsafe_allow_html=True)


def insight_box(big, text):
    st.markdown(f'<div class="insight-box"><div class="big">{big}</div>'
                f'<div class="txt">{text}</div></div>', unsafe_allow_html=True)
