"""Colours, Plotly styling and CSS for the Fremantle Dockers dashboard.

Purple and white theme. The categorical palette was validated for the
lightness band, chroma floor, adjacent-pair colour-vision separation and
contrast against a white surface, so Fremantle vs Opposition reads cleanly
for everyone. Colour follows the entity (Freo is always purple), never rank.
"""

import streamlit as st

COLORS = {
    "freo": "#7C3AED",     # Fremantle (categorical slot 1)
    "opp": "#C25E12",      # Opposition (categorical slot 2)
    "teal": "#0D9488",     # third series
    "magenta": "#BE185D",  # fourth series
    "win": "#15803D",
    "loss": "#DC2626",
    "ink": "#1F2937",
    "muted": "#6B7280",
    "grid": "#E7E3EF",
    "brand": "#2A0A4A",    # deep Freo purple for headings and the top band
    "brand2": "#4C1D95",
}

# Fixed categorical order. A series is assigned a slot by identity and keeps it.
PALETTE = [COLORS["freo"], COLORS["opp"], COLORS["teal"], COLORS["magenta"]]

FONT = "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"


def style_fig(fig, y_title="", unified=True, height=380):
    """Apply the shared chart look: white surface, recessive grid and axes,
    a legend across the top, and a single y axis (never a dual axis)."""
    fig.update_layout(
        template="plotly_white",
        font=dict(family=FONT, color=COLORS["ink"], size=13),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=8, r=12, t=34, b=8),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(color=COLORS["muted"], size=12),
        ),
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
          .block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1250px; }
          .freo-band {
            background: linear-gradient(100deg, #2A0A4A 0%, #4C1D95 55%, #6D28D9 100%);
            color: #FFFFFF; padding: 18px 24px; border-radius: 14px; margin-bottom: 18px;
          }
          .freo-band h1 { color:#FFFFFF; font-size: 1.55rem; margin:0; font-weight:700; letter-spacing:.2px; }
          .freo-band p { color:#E9D5FF; margin:.25rem 0 0; font-size:.9rem; }
          section[data-testid="stSidebar"] { background: #F5F1FB; }
          section[data-testid="stSidebar"] h2 { color:#2A0A4A; }
          h2, h3 { color:#2A0A4A; }
          .results-strip { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 4px; }
          .chip {
            border-radius:8px; padding:6px 9px; min-width:74px; text-align:center;
            font-size:.72rem; line-height:1.25; color:#fff;
          }
          .chip .rnd { font-weight:700; font-size:.7rem; opacity:.92; }
          .chip .opp { display:block; font-weight:600; }
          .chip .mgn { display:block; opacity:.95; }
          .insight {
            background:#F5F1FB; border-left:4px solid #7C3AED; border-radius:8px;
            padding:12px 14px; margin:4px 0 10px; color:#1F2937; font-size:.92rem;
          }
          .insight b { color:#4C1D95; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def band(title, subtitle):
    st.markdown(
        f'<div class="freo-band"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )
