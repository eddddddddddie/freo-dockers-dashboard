"""Plotly charts for the Coach View. Sized for one 1440x900 screen: small
fixed heights, minimal chrome, detail on hover. One y axis only; a legend for
two or more series."""

import plotly.graph_objects as go
from theme import COLORS, style_fig



def win_conditions_bars(wc, height):
    """Win rate when Freo win vs lose the count on each stat."""
    fig = go.Figure()
    for key, name, color in [("ahead", "Freo won it", COLORS["freo"]),
                             ("behind", "Opp won it", COLORS["opp"])]:
        rate = wc[f"{key}_winrate"]
        n = wc[f"{key}_games"]
        fig.add_trace(go.Bar(
            y=wc["stat"], x=rate, name=name, orientation="h",
            marker=dict(color=color, cornerradius=3),
            text=[f"{r:.0f}%" if r == r and r is not None else "" for r in rate],
            textposition="outside", textfont=dict(size=10, color=COLORS["ink"]),
            customdata=n,
            hovertemplate="%{y}: " + name + "<br>Won <b>%{x:.0f}%</b> of "
                          "%{customdata} games<extra></extra>",
        ))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08, showlegend=False,
                      margin=dict(l=4, r=4, t=4, b=4))
    fig.update_xaxes(range=[0, 118], showticklabels=False, showgrid=False)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=11))
    return fig


def quarter_bars(qp, height):
    """Average points for and against in each quarter."""
    fig = go.Figure()
    for col, name, color in [("freo", "Fremantle", COLORS["freo"]),
                             ("opp", "Opposition", COLORS["opp"])]:
        fig.add_trace(go.Bar(
            x=qp["quarter"], y=qp[col], name=name,
            marker=dict(color=color, cornerradius=3),
            customdata=qp[["margin", "won", "games"]].values,
            hovertemplate="%{x} " + name + ": <b>%{y:.1f}</b> pts avg<br>"
                          "Freo won %{customdata[1]} of %{customdata[2]} "
                          "(avg %{customdata[0]:+.1f})<extra></extra>",
        ))
    for _, r in qp.iterrows():
        fig.add_annotation(x=r["quarter"], y=max(r["freo"], r["opp"]),
                           text=f"{r['margin']:+.1f}", showarrow=False, yshift=10,
                           font=dict(size=11, color=COLORS["ink"]))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.06, showlegend=False,
                      margin=dict(l=4, r=6, t=8, b=4))
    top = max(qp["freo"].max(), qp["opp"].max())
    fig.update_yaxes(range=[0, top * 1.22])
    return fig


# One-hue sequential purple, light to dark.
FORM_SCALE = [[0, "#F5F1FB"], [0.25, "#DDD0F7"], [0.5, "#B79AEE"],
              [0.75, "#7C3AED"], [1, "#3B0F7A"]]


def form_heatmap(vals, avgs, stat_label, height):
    """Player form: each cell is the player's number in that game, shaded on a
    light to dark purple scale by that number as a % of the player's own season
    average (half the average or less is lightest, 1.5x or more darkest).
    Plotly picks a contrasting text colour per cell."""
    pct = vals.div(avgs.clip(lower=0.1), axis=0) * 100
    rows = [f"{p}  ({a:.1f})" for p, a in avgs.items()]
    text = vals.map(lambda v: "" if v != v else f"{v:.0f}").values
    fig = go.Figure(go.Heatmap(
        z=pct.values, x=list(vals.columns), y=rows, text=text,
        texttemplate="%{text}", textfont=dict(size=11),
        colorscale=FORM_SCALE, zmin=50, zmax=150, xgap=2, ygap=2, showscale=False,
        customdata=vals.values,
        hovertemplate="%{y}<br>%{x}: <b>%{customdata:.0f}</b> " + stat_label.lower() +
                      "<br>%{z:.0f}% of season avg<extra></extra>",
        hoverongaps=False,
    ))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=4, t=4, b=4))
    fig.update_xaxes(side="top", tickfont=dict(size=10))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=11))
    return fig


# Diverging: opposition orange <- neutral grey -> Freo purple. The poles are the
# two entity colours, so "purple = Freo won it" reads the same as everywhere else.
DIVERGING = [[0, COLORS["opp"]], [0.25, "#E9B48A"], [0.5, "#F0EFEC"],
             [0.75, "#B79AEE"], [1, COLORS["freo"]]]


def game_strip(rows, z, hover, labels, results, height):
    """One column per game: a W/L row on top, then margin and key differentials,
    each row shaded by who won it (scaled to that row's biggest gap)."""
    fig = go.Figure()
    fig.add_trace(go.Heatmap(
        z=[z_row for z_row in z], x=labels, y=rows, customdata=hover,
        colorscale=DIVERGING, zmin=-1, zmax=1, xgap=1.5, ygap=2, showscale=False,
        hovertemplate="%{customdata}<extra></extra>",
    ))
    # Result row: its own trace so it can use win/loss colours and a letter.
    fig.add_trace(go.Heatmap(
        z=[[1 if r == "W" else 0 for r in results]], x=labels, y=["Result"],
        text=[results], texttemplate="%{text}", textfont=dict(size=10, color="#FFFFFF"),
        colorscale=[[0, COLORS["loss"]], [1, COLORS["win"]]], zmin=0, zmax=1,
        xgap=1.5, ygap=2, showscale=False, hoverinfo="skip",
    ))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=4, t=8, b=4))
    fig.update_xaxes(tickangle=-90, tickfont=dict(size=9), showgrid=False)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=11),
                     categoryorder="array", categoryarray=["Result"] + rows)
    return fig


def drivers_bar(dr, height):
    """Correlation of each differential with margin, strongest first. Positive
    (goes with winning) in Freo purple, negative in muted grey."""
    colors = [COLORS["freo"] if r > 0 else "#9CA3AF" for r in dr["r"]]
    fig = go.Figure(go.Bar(
        y=dr["stat"], x=dr["r"], orientation="h",
        marker=dict(color=colors, cornerradius=3),
        text=[f"{r:+.2f}" if r > 0 else "" for r in dr["r"]], textposition="outside",
        textfont=dict(size=10, color=COLORS["ink"]), cliponaxis=False,
        customdata=dr["games"],
        hovertemplate="%{y} differential vs margin<br>r = <b>%{x:+.2f}</b> over "
                      "%{customdata} games<extra></extra>",
    ))
    # Negative values labelled just right of zero, clear of the stat names.
    for stat, r in zip(dr["stat"], dr["r"]):
        if r <= 0:
            fig.add_annotation(x=0, y=stat, text=f"{r:+.2f}", showarrow=False,
                               xanchor="left", xshift=4, font=dict(size=10, color=COLORS["ink"]))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=30, t=4, b=4), bargap=0.3)
    fig.update_xaxes(range=[-0.8, 1.15], showticklabels=False, showgrid=False,
                     zeroline=True, zerolinecolor=COLORS["grid"], zerolinewidth=1)
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11))
    return fig


def running_margin_lines(rm, height):
    """Average margin at each quarter break in wins and in losses."""
    fig = go.Figure()
    qs = ["Q1", "Q2", "Q3", "Q4"]
    for res, name, color, pos in [("W", "Wins", COLORS["win"], "top center"),
                                  ("L", "Losses", COLORS["loss"], "bottom center")]:
        if res not in rm.index:
            continue
        y = rm.loc[res, qs].values
        n = int(rm.loc[res, "games"])
        fig.add_trace(go.Scatter(
            x=qs, y=y, name=name, mode="lines+markers+text",
            line=dict(color=color, width=2), marker=dict(size=8),
            text=[f"{v:+.1f}" for v in y], textposition=pos,
            textfont=dict(size=10, color=COLORS["ink"]),
            hovertemplate=f"{name} ({n} games)<br>%{{x}} break: <b>%{{y:+.1f}}</b><extra></extra>",
        ))
    fig.add_hline(y=0, line=dict(color=COLORS["muted"], width=1, dash="dot"))
    fig = style_fig(fig, "Avg margin", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=10, t=14, b=4))
    lo, hi = float(rm[qs].min().min()), float(rm[qs].max().max())
    pad = (hi - lo) * 0.18 or 5
    fig.update_yaxes(range=[min(lo, 0) - pad, max(hi, 0) + pad])
    return fig


def player_map(pa, xcol, ycol, xlab, ylab, size_col, height, n_labels=10):
    """Every player's per game averages on two stats. Dotted lines at the team
    median split the map into four quadrants; the leaders on either axis are
    labelled directly, the rest on hover."""
    size = pa[size_col] if size_col in pa.columns else pa["games"]
    sref = float(size.max() or 1)
    lead = set(pa[xcol].nlargest(n_labels // 2).index) | set(pa[ycol].nlargest(n_labels // 2).index)
    fig = go.Figure(go.Scatter(
        x=pa[xcol], y=pa[ycol], mode="markers+text",
        text=[p if p in lead else "" for p in pa.index], textposition="top center",
        textfont=dict(size=10, color=COLORS["ink"]),
        marker=dict(size=8 + 14 * (size / sref) ** 2, color=COLORS["freo"], opacity=0.75,
                    line=dict(color="#FFFFFF", width=2)),
        customdata=list(zip(pa.index, pa["games"], size.round(0))),
        hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]} games)<br>"
                      + xlab + ": %{x:.1f}<br>" + ylab + ": %{y:.1f}<extra></extra>",
    ))
    fig.add_vline(x=pa[xcol].median(), line=dict(color=COLORS["muted"], width=1, dash="dot"))
    fig.add_hline(y=pa[ycol].median(), line=dict(color=COLORS["muted"], width=1, dash="dot"))
    fig = style_fig(fig, ylab + " per game", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=8, r=16, t=16, b=8))
    fig.update_xaxes(title=dict(text=xlab + " per game", font=dict(color=COLORS["muted"], size=11)),
                     showgrid=True, gridcolor=COLORS["grid"])
    return fig


def _spread(values, gap):
    """Label positions: the values, pushed apart to at least `gap`."""
    order = values.sort_values()
    pos, last = {}, None
    for name, v in order.items():
        y = v if last is None else max(v, last + gap)
        pos[name] = y
        last = y
    return pos


def slope_chart(yoy, s0, s1, stat_label, height):
    """Per game average in two seasons, one line per player. Up in Freo purple,
    down in muted grey; names and values labelled at the ends."""
    fig = go.Figure()
    lo = float(min(yoy["before"].min(), yoy["after"].min()))
    hi = float(max(yoy["before"].max(), yoy["after"].max()))
    gap = (hi - lo) / max(height - 40, 1) * 14  # one label line in data units
    y_right = _spread(yoy["after"], gap)
    y_left = _spread(yoy["before"], gap)
    for name, r in yoy.iterrows():
        up = r["change"] >= 0
        color = COLORS["freo"] if up else "#9CA3AF"
        fig.add_trace(go.Scatter(
            x=[str(s0), str(s1)], y=[r["before"], r["after"]], mode="lines+markers",
            line=dict(color=color, width=2), marker=dict(size=8, color=color),
            hovertemplate=f"<b>{name}</b><br>%{{x}}: %{{y:.1f}} {stat_label.lower()} a game"
                          f"<br>Change {r['change']:+.1f}<extra></extra>",
            showlegend=False,
        ))
        fig.add_annotation(x=1, y=y_right[name], text=f"{name}  {r['after']:.1f} ({r['change']:+.1f})",
                           showarrow=False, xanchor="left", xshift=10, font=dict(size=10, color=COLORS["ink"]))
        fig.add_annotation(x=0, y=y_left[name], text=f"{r['before']:.1f}", showarrow=False,
                           xanchor="right", xshift=-10, font=dict(size=10, color=COLORS["muted"]))
    fig = style_fig(fig, stat_label + " per game", unified=False, height=height)
    fig.update_layout(margin=dict(l=8, r=230, t=16, b=8))
    # Season labels are categories, not numbers; pad so end labels fit.
    fig.update_xaxes(type="category", tickfont=dict(size=12), range=[-0.35, 1.05])
    return fig
