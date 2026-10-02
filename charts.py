"""Plotly charts for the Coach View. Sized for one 1440x900 screen: small
fixed heights, minimal chrome, detail on hover. One y axis only; a legend for
two or more series."""

import plotly.graph_objects as go
from theme import COLORS, DIVERGE, RAMP, SERIES, style_fig

import data as D

# Highlighting the finding: the marks a card's takeaway names keep full strength,
# the rest drop to this opacity (same hue, so identity never changes), and their
# labels go from ink to muted. focus=None draws every mark at full strength.
FADE = 0.4


def _alpha(keys, focus):
    focus = set(focus) if focus is not None and not isinstance(focus, str) else {focus}
    return [1.0 if (None in focus or k in focus) else FADE for k in keys]


def _ink(alphas):
    return [COLORS["ink"] if a == 1.0 else COLORS["muted"] for a in alphas]


def _bold(labels, focus):
    focus = set(focus) if focus is not None and not isinstance(focus, str) else {focus}
    return [f"<b>{l}</b>" if l in focus else l for l in labels]


def win_conditions_bars(wc, height, names=("Freo won it", "Opp won it"), colors=None,
                        focus=None):
    """Win rate when a side wins vs loses the count on each stat. focus: the stat
    the takeaway names (the biggest swing)."""
    colors = colors or (COLORS["freo"], COLORS["opp"])
    alpha = _alpha(wc["stat"], focus)
    fig = go.Figure()
    for key, name, color in [("ahead", names[0], colors[0]), ("behind", names[1], colors[1])]:
        rate = wc[f"{key}_winrate"]
        n = wc[f"{key}_games"]
        fig.add_trace(go.Bar(
            y=wc["stat"], x=rate, name=name, orientation="h",
            marker=dict(color=color, cornerradius=3, opacity=alpha),
            text=[f"{r:.0f}%" if r == r and r is not None else "" for r in rate],
            textposition="outside", textfont=dict(size=10, color=_ink(alpha)),
            customdata=n,
            hovertemplate="%{y}: " + name + "<br>Won <b>%{x:.0f}%</b> of "
                          "%{customdata} games<extra></extra>",
        ))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08, showlegend=False,
                      margin=dict(l=4, r=4, t=4, b=4))
    fig.update_xaxes(range=[0, 118], showticklabels=False, showgrid=False)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=11),
                     tickmode="array", tickvals=list(wc["stat"]),
                     ticktext=_bold(list(wc["stat"]), focus if focus is not None else []))
    return fig


def _click_layer(fig, xs, ys, hover, size=26):
    """Invisible markers over heatmap cells. Streamlit only reports clicks on
    point marks, not heatmap cells, so these carry the click (and the hover
    text) for each cell. hover: text per (y, x), row-major. The axes are pinned
    to the cells, or the markers would pad them and leave an empty band."""
    fig.add_trace(go.Scatter(
        x=[x for _ in ys for x in xs], y=[y for y in ys for _ in xs], mode="markers",
        marker=dict(symbol="square", size=size, opacity=0.001), customdata=hover,
        hovertemplate="%{customdata}<extra></extra>", showlegend=False))
    fig.update_xaxes(range=[-0.5, len(xs) - 0.5])
    fig.update_yaxes(range=[len(ys) - 0.5, -0.5], autorange=False)  # top row first
    return fig


def _inline_key(fig, items):
    """A one-line colour key drawn inside the chart (top left), for cards whose
    title row has no room for one."""
    text = "  ".join(f'<span style="color:{c}">■</span> {l}' for l, c in items)
    fig.add_annotation(text=text, xref="paper", yref="paper", x=0, y=1.0, xanchor="left",
                       yanchor="bottom", showarrow=False, font=dict(size=10, color=COLORS["muted"]))
    fig.update_layout(margin=dict(t=22))
    return fig


def quarter_bars(qp, height, names=("Fremantle", "Opposition"), colors=None, focus=None):
    """Average points for and against in each quarter. names/colors let the
    scout report show an opponent (orange) against the teams it played (grey).
    focus: (best quarter, worst quarter): the best stays strong, the worst's
    margin is labelled in ink, the rest step back."""
    colors = colors or (COLORS["freo"], COLORS["opp"])
    best, worst = focus if focus else (None, None)
    alpha = _alpha(qp["quarter"], best)
    fig = go.Figure()
    for col, name, color in [("freo", names[0], colors[0]), ("opp", names[1], colors[1])]:
        fig.add_trace(go.Bar(
            x=qp["quarter"], y=qp[col], name=name,
            marker=dict(color=color, cornerradius=3, opacity=alpha),
            customdata=qp[["margin", "won", "games"]].values,
            hovertemplate="%{x} " + name + ": <b>%{y:.1f}</b> pts avg<br>"
                          + names[0].split()[0] + " won %{customdata[1]} of %{customdata[2]} "
                          "(avg %{customdata[0]:+.1f})<extra></extra>",
        ))
    for _, r in qp.iterrows():
        q = r["quarter"]
        strong = best is None or q in (best, worst)
        fig.add_annotation(x=q, y=max(r["freo"], r["opp"]),
                           text=f"<b>{r['margin']:+.1f}</b>" if q == best else f"{r['margin']:+.1f}",
                           showarrow=False, yshift=10,
                           font=dict(size=12 if q == best else 11,
                                     color=COLORS["ink"] if strong else COLORS["muted"]))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.06, showlegend=False,
                      margin=dict(l=4, r=6, t=8, b=4))
    top = max(qp["freo"].max(), qp["opp"].max())
    fig.update_yaxes(range=[0, top * 1.22])
    if best is not None:
        fig.update_xaxes(tickmode="array", tickvals=list(qp["quarter"]),
                         ticktext=_bold(list(qp["quarter"]), best))
    short = [n if len(n) <= 10 else D.abbr(n) for n in names]
    return _inline_key(fig, [(short[0], colors[0]), (short[1], colors[1])])


# One-hue sequential purple, light to dark.
FORM_SCALE = [[i / (len(RAMP) - 1), c] for i, c in enumerate(RAMP)]


def form_dumbbell(last3, avgs, pct, stat_label, height, focus=None):
    """Who's up, who's down: per player, his season average (hollow ring) to his
    last-3 average (filled: purple up, grey down), sorted by the change, which is
    labelled in a column at the right. focus: the takeaway's hottest player."""
    order = pct.sort_values(ascending=False).index.tolist()
    # As many rows as fit at about 17px each: the biggest risers and the biggest drops.
    fit = max(4, int((height - 40) / 17))
    if len(order) > fit:
        order = order[: (fit + 1) // 2] + order[len(order) - fit // 2:]
    alpha = _alpha(order, focus) if focus is not None else [1.0] * len(order)
    fig = go.Figure()
    for p in order:
        fig.add_trace(go.Scatter(x=[avgs[p], last3[p]], y=[p, p], mode="lines", hoverinfo="skip",
                                 showlegend=False, line=dict(color=COLORS["grid"], width=4)))
    fig.add_trace(go.Scatter(
        x=[avgs[p] for p in order], y=order, mode="markers", showlegend=False, hoverinfo="skip",
        marker=dict(size=10, color="#FFFFFF", line=dict(color=COLORS["muted"], width=2))))
    up = [pct[p] >= 100 for p in order]
    fig.add_trace(go.Scatter(
        x=[last3[p] for p in order], y=order, mode="markers", showlegend=False,
        marker=dict(size=11, color=[COLORS["freo"] if u else COLORS["neutral"] for u in up],
                    line=dict(color="#FFFFFF", width=1.5)),
        customdata=[[avgs[p], pct[p] - 100] for p in order],
        hovertemplate="<b>%{y}</b><br>Last 3: %{x:.1f} " + stat_label.lower() + " a game<br>"
                      "Season: %{customdata[0]:.1f} (%{customdata[1]:+.0f}%)<br>"
                      "Click for the player profile<extra></extra>"))
    for p, a in zip(order, alpha):
        ch = pct[p] - 100
        fig.add_annotation(x=1, xref="paper", y=p, xanchor="left", xshift=8, showarrow=False,
                           text=f"<b>{ch:+.0f}%</b>" if p == focus else f"{ch:+.0f}%",
                           font=dict(size=11, color=COLORS["ink"] if a == 1 else COLORS["muted"]))
    fig = style_fig(fig, stat_label + " a game", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=44, t=16, b=4))
    fig.add_annotation(x=1, xref="paper", y=1, yref="paper", text="change", showarrow=False,
                       xanchor="left", xshift=4, yanchor="bottom",
                       font=dict(size=10, color=COLORS["muted"]))
    fig.update_xaxes(title=None, showgrid=True, gridcolor=COLORS["grid"], tickfont=dict(size=10))
    fig.update_yaxes(title=None, autorange="reversed", showgrid=False, tickfont=dict(size=12),
                     tickmode="array", tickvals=order, ticktext=_bold(order, focus or []))
    return fig


# Diverging: opposition orange <- neutral grey -> Freo purple. The poles are the
# two entity colours, so "purple = Freo won it" reads the same as everywhere else.
DIVERGING = [[i / (len(DIVERGE) - 1), c] for i, c in enumerate(DIVERGE)]


def game_strip(rows, z, hover, labels, results, height, focus=None, show_x=True):
    """show_x False (a narrow card): no game labels and no W/L letters, which
    wouldn't fit; the hover has them."""
    """One column per game: a W/L row on top, then margin and key differentials,
    each row shaded by who won it (scaled to that row's biggest gap)."""
    fig = go.Figure()
    fig.add_trace(go.Heatmap(
        z=[z_row for z_row in z], x=labels, y=rows, customdata=hover,
        colorscale=DIVERGING, zmin=-1, zmax=1, xgap=1.5, ygap=2, showscale=False,
        hoverinfo="skip",
    ))
    # Result row: its own trace so it can use win/loss colours and a letter.
    fig.add_trace(go.Heatmap(
        z=[[{"W": 1, "L": 0}.get(r, 0.5) for r in results]], x=labels, y=["Result"],
        text=[results] if show_x else None, texttemplate="%{text}" if show_x else None,
        textfont=dict(size=10, color="#FFFFFF"),
        colorscale=[[0, COLORS["loss"]], [0.45, COLORS["loss"]], [0.45, COLORS["neutral"]],
                    [0.55, COLORS["neutral"]], [0.55, COLORS["win"]], [1, COLORS["win"]]],
        zmin=0, zmax=1,
        xgap=1.5, ygap=2, showscale=False, hoverinfo="skip",
    ))
    tips = [[f"<b>{x}</b>: {r} · click to open this game" for x, r in zip(labels, results)]] + \
        [[f"{h}<br>Click to open this game" for h in row] for row in hover]
    _click_layer(fig, labels, ["Result"] + rows, [t for row in tips for t in row], size=18)
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=4, t=8, b=4))
    fig.update_xaxes(tickangle=-90, tickfont=dict(size=10), showgrid=False,
                     showticklabels=show_x)
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11),
                     categoryorder="array", categoryarray=["Result"] + rows,
                     tickmode="array", tickvals=["Result"] + rows,
                     ticktext=_bold(["Result"] + rows, focus if focus is not None else []))
    return fig


def drivers_bar(dr, height, focus=None):
    """Correlation of each differential with margin, strongest first. Positive
    (goes with winning) in Freo purple, negative in muted grey. focus: the stat
    the takeaway names (the strongest)."""
    colors = [COLORS["freo"] if r > 0 else COLORS["neutral"] for r in dr["r"]]
    alpha = _alpha(dr["stat"], focus)
    fig = go.Figure(go.Bar(
        y=dr["stat"], x=dr["r"], orientation="h",
        marker=dict(color=colors, cornerradius=3, opacity=alpha),
        text=[f"{r:+.2f}" if r > 0 else "" for r in dr["r"]], textposition="outside",
        textfont=dict(size=10, color=_ink(alpha)), cliponaxis=False,
        hoverinfo="skip",
    ))
    # Clicks on bars aren't reported by Streamlit, so invisible point markers along
    # each row carry the click (to open that stat's scatter) and the hover.
    fig.add_trace(go.Scatter(
        x=[r / 2 for r in dr["r"]], y=dr["stat"], mode="markers", showlegend=False,
        marker=dict(symbol="square", size=16, opacity=0.001), customdata=dr[["r", "games"]].values,
        hovertemplate="%{y} differential vs margin<br>r = <b>%{customdata[0]:+.2f}</b> over "
                      "%{customdata[1]} games<br>Click for every game<extra></extra>"))
    # Negative values labelled just right of zero, clear of the stat names.
    for stat, r, a in zip(dr["stat"], dr["r"], alpha):
        if r <= 0:
            fig.add_annotation(x=0, y=stat, text=f"{r:+.2f}", showarrow=False,
                               xanchor="left", xshift=4,
                               font=dict(size=10, color=COLORS["ink"] if a == 1 else COLORS["muted"]))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=30, t=4, b=4), bargap=0.3)
    fig.update_xaxes(range=[-0.8, 1.15], showticklabels=False, showgrid=False,
                     zeroline=True, zerolinecolor=COLORS["grid"], zerolinewidth=1)
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11), tickmode="array",
                     tickvals=list(dr["stat"]), ticktext=_bold(list(dr["stat"]), focus or []))
    return fig


def win_dumbbell(wc, height, names=("Freo won it", "Opp won it"), colors=None, focus=None):
    """Where we win, as a dumbbell: on each stat, the win rate when the other side
    won the count (left dot) to the win rate when Freo won it (right dot), sorted
    by the gap, which is labelled at the end of each row. focus: the takeaway's
    stat (the biggest swing) keeps full strength and its two rates labelled."""
    colors = colors or (COLORS["freo"], COLORS["opp"])
    wc = wc.dropna(subset=["ahead_winrate", "behind_winrate"]).copy()
    wc["swing"] = wc["ahead_winrate"] - wc["behind_winrate"]
    wc = wc.sort_values("swing", ascending=False)
    stats = list(wc["stat"])
    alpha = _alpha(stats, focus)
    fig = go.Figure()
    for (_, r), a in zip(wc.iterrows(), alpha):
        fig.add_trace(go.Scatter(x=[r["behind_winrate"], r["ahead_winrate"]], y=[r["stat"]] * 2,
                                 mode="lines", hoverinfo="skip", showlegend=False, opacity=a,
                                 line=dict(color=COLORS["muted"] if a == 1 else COLORS["grid"],
                                           width=3)))
    for key, name, color in (("behind", names[1], colors[1]), ("ahead", names[0], colors[0])):
        fig.add_trace(go.Scatter(
            x=wc[f"{key}_winrate"], y=stats, mode="markers", name=name,
            marker=dict(size=11, color=color, opacity=alpha, line=dict(color="#FFFFFF", width=2)),
            customdata=wc[[f"{key}_games"]].values,
            hovertemplate="%{y}: " + name + "<br>Won <b>%{x:.0f}%</b> of %{customdata[0]} "
                          "games<extra></extra>"))
    for (_, r), a in zip(wc.iterrows(), alpha):
        strong = a == 1 and focus is not None
        fig.add_annotation(x=1, xref="paper", y=r["stat"], text=(f"<b>{r['swing']:+.0f}</b>" if strong
                           else f"{r['swing']:+.0f}"), showarrow=False, xanchor="left", xshift=8,
                           font=dict(size=11, color=COLORS["ink"] if a == 1 else COLORS["muted"]))
        if strong:   # the focus row's two rates, just above their dots
            for v in (r["behind_winrate"], r["ahead_winrate"]):
                fig.add_annotation(x=v, y=r["stat"], text=f"{v:.0f}%", showarrow=False,
                                   yanchor="bottom", yshift=5,
                                   font=dict(size=10, color=COLORS["ink"]))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=36, t=16, b=4))  # r: the swing column
    fig.update_xaxes(range=[-6, 106], tickvals=[0, 50, 100], ticktext=["0%", "50%", "100%"],
                     showgrid=True, gridcolor=COLORS["grid"], tickfont=dict(size=10))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=11), tickmode="array",
                     tickvals=stats, ticktext=_bold(stats, focus if focus is not None else []))
    fig.add_annotation(x=1, xref="paper", y=1, yref="paper", text="swing", showarrow=False,
                       xanchor="left", xshift=4, yanchor="bottom",
                       font=dict(size=10, color=COLORS["muted"]))
    return fig


def driver_scatter(pts, fit, stat, height):
    """One margin driver up close: every game's differential (across) against the
    final margin (up), green win / red loss (and above / below the zero line),
    a least-squares line, r labelled. Clicking a game opens it."""
    colors = [{"W": COLORS["win"], "L": COLORS["loss"]}.get(r, COLORS["neutral"]) for r in pts["result"]]
    fig = go.Figure()
    lo, hi = float(pts["diff"].min()), float(pts["diff"].max())
    fig.add_trace(go.Scatter(x=[lo, hi], y=[fit["intercept"] + fit["slope"] * lo,
                                            fit["intercept"] + fit["slope"] * hi],
                             mode="lines", hoverinfo="skip", showlegend=False,
                             line=dict(color=COLORS["muted"], width=1.5, dash="dash")))
    fig.add_trace(go.Scatter(
        x=pts["diff"], y=pts["margin"], mode="markers", showlegend=False,
        marker=dict(size=9, color=colors, line=dict(color="#FFFFFF", width=1.5)),
        customdata=pts[["label", "opponent", "result"]].values,
        hovertemplate="<b>%{customdata[0]}</b> v %{customdata[1]} (%{customdata[2]})<br>"
                      + stat + " diff %{x:+,.0f} · margin %{y:+d}<br>Click to open this game"
                      "<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=COLORS["muted"], width=1, dash="dot"))
    fig.add_vline(x=0, line=dict(color=COLORS["muted"], width=1, dash="dot"))
    fig.add_annotation(x=0, xref="paper", y=1, yref="paper", xanchor="left", yanchor="top",
                       text=f"r {fit['r']:+.2f} · {fit['games']} games", showarrow=False,
                       font=dict(size=11, color=COLORS["ink"]))
    fig = style_fig(fig, "Final margin", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=8, t=8, b=4))
    fig.update_xaxes(title=dict(text=f"{stat} differential", font=dict(color=COLORS["muted"], size=11)),
                     showgrid=True, gridcolor=COLORS["grid"], zeroline=False)
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
    return _inline_key(fig, [("Wins", COLORS["win"]), ("Losses", COLORS["loss"])])


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
        color = COLORS["freo"] if up else COLORS["neutral"]
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


# ---- Match mode ---------------------------------------------------------------
def game_flow_lines(game, avg, height, others=None):
    """Running margin at each break in one game, against the season's average
    running margin in wins and in losses (thin dashed reference lines), with
    the season's other games faint grey behind (no hover)."""
    qs = ["Start", "Q1", "Q2", "Q3", "Q4"]
    fig = go.Figure()
    others = others if others is not None else []
    for _, row in (others.iterrows() if len(others) else []):
        fig.add_trace(go.Scatter(
            x=qs, y=[0] + row.tolist(), mode="lines", hoverinfo="skip", showlegend=False,
            line=dict(color=COLORS["neutral"], width=1), opacity=0.28))
    for res, name, color in [("W", "Avg win", COLORS["win"]), ("L", "Avg loss", COLORS["loss"])]:
        if res in avg.index:
            fig.add_trace(go.Scatter(
                x=qs, y=[0] + avg.loc[res].round(1).tolist(), name=name, mode="lines",
                line=dict(color=color, width=1.5, dash="dash"),
                hovertemplate=name + " at %{x}: %{y:+.1f}<extra></extra>"))
    y = [0] + game.tolist()
    fig.add_trace(go.Scatter(
        x=qs, y=y, name="This game", mode="lines+markers+text",
        line=dict(color=COLORS["freo"], width=3), marker=dict(size=8),
        text=[""] + [f"{v:+.0f}" if v else "0" for v in game], textposition="top center",
        textfont=dict(size=11, color=COLORS["ink"]),
        hovertemplate="This game at %{x}: <b>%{y:+.0f}</b><extra></extra>"))
    fig.add_hline(y=0, line=dict(color=COLORS["muted"], width=1, dash="dot"))
    fig = style_fig(fig, "Margin", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=10, t=14, b=4))
    lo = min(min(y), float(avg.min().min()) if len(avg) else 0,
             float(others.min().min()) if len(others) else 0)
    hi = max(max(y), float(avg.max().max()) if len(avg) else 0,
             float(others.max().max()) if len(others) else 0)
    pad = (hi - lo) * 0.15 or 5
    fig.update_yaxes(range=[lo - pad, hi + pad])
    return fig


def match_player_grid(vals, pct, labels, height):
    """Every Freo player in one game: the number, shaded light to dark purple by
    that number as a % of the player's own season average."""
    text = vals.map(lambda v: "" if v != v else f"{v:.0f}").values
    fig = go.Figure(go.Heatmap(
        z=pct.values, x=labels, y=list(vals.index), text=text,
        texttemplate="%{text}", textfont=dict(size=11),
        colorscale=FORM_SCALE, zmin=50, zmax=150, xgap=2, ygap=2, showscale=False,
        hoverinfo="skip",
    ))
    tips = [f"<b>{p}</b> · {lbl}: {v:.0f} ({pc:.0f}% of season avg)<br>Click for the player profile"
            for p, row, prow in zip(vals.index, vals.values, pct.values)
            for lbl, v, pc in zip(labels, row, prow)]
    _click_layer(fig, labels, list(vals.index), tips, size=20)
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=4, t=4, b=4))
    fig.update_xaxes(side="top", tickfont=dict(size=11))
    fig.update_yaxes(showgrid=False, tickfont=dict(size=12),
                     tickmode="array", tickvals=list(vals.index), ticktext=list(vals.index))
    return fig


# Below this season average a stat is too small for a % to mean much (two tackles
# instead of one is "200%"): those players get no standout label on it.
VS_SELF_MIN_AVG = {"disposals": 5, "contested_poss": 2, "metres_gained": 60, "tackles": 1.5,
                   "pressure_acts": 6, "score_involvements": 1.5, "marks": 1.5,
                   "clearances": 1, "inside_50s": 1.5}


def vs_self_dots(vals, pct, avgs, stats, height, rp=None, standout=30, ticks=True):
    """Who played above themselves: one narrow column per stat, a dot per player
    placed by this game as a % of his own season average (the centre line).
    Purple 15%+ above, grey 15%+ below, light purple between; the number is
    labelled only for standouts (standout % or more either way, on a season
    average big enough for a % to mean something). Rows in the order given
    (best rated first); rp: rating points, shown with the name."""
    from plotly.subplots import make_subplots
    players = list(vals.index)
    n = len(stats)
    fig = make_subplots(rows=1, cols=n, shared_yaxes=True, horizontal_spacing=0.014,
                        subplot_titles=[lbl for lbl, _ in stats])
    for j, (lbl, col) in enumerate(stats, start=1):
        p, v, a = pct[col], vals[col], avgs[col]
        shown = p.clip(28, 172)        # beyond ±72% sits just inside the column edge
        colors = [COLORS["freo"] if x >= 115 else COLORS["neutral"] if x <= 85 else RAMP[1]
                  for x in p.fillna(100)]
        big = (p - 100).abs() >= standout
        big &= a >= VS_SELF_MIN_AVG.get(col, 0)
        text = [f"{x:.0f}" if b else "" for x, b in zip(v, big)]
        # Labels on the inner side (towards the average line), so none run off the column.
        pos = ["middle left" if x >= 100 else "middle right" for x in p.fillna(100)]
        fig.add_trace(go.Scatter(
            x=shown, y=players, mode="markers+text", text=text, textposition=pos,
            textfont=dict(size=10, color=COLORS["ink"]), showlegend=False,
            marker=dict(size=9, color=colors, line=dict(color="#FFFFFF", width=1.5)),
            customdata=list(zip(v, a, p)),
            hovertemplate="<b>%{y}</b> · " + lbl + ": %{customdata[0]:.0f} (season avg "
                          "%{customdata[1]:.1f}, %{customdata[2]:.0f}%)<br>Click for the player "
                          "profile<extra></extra>"), row=1, col=j)
        fig.add_vline(x=100, line=dict(color=COLORS["muted"], width=1), row=1, col=j)
        fig.update_xaxes(range=[15, 185], tickvals=[50, 100, 150], ticktext=["-50%", "avg", "+50%"],
                         tickfont=dict(size=9, color=COLORS["muted"]), showgrid=False,
                         showticklabels=ticks, tickangle=0,
                         zeroline=False, fixedrange=True, row=1, col=j)
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=4, t=20, b=4))
    for ann in fig.layout.annotations:   # the column titles
        ann.font = dict(size=11, color=COLORS["ink"])
    names = [f"{pl}  {int(r)}" if rp is not None and r == r else pl
             for pl, r in zip(players, rp if rp is not None else [None] * len(players))]
    fig.update_yaxes(autorange="reversed", tickmode="array", tickvals=players, ticktext=names,
                     tickfont=dict(size=11), showgrid=True, gridcolor=COLORS["grid"],
                     fixedrange=True)
    return fig


# ---- Quarter-time check ---------------------------------------------------------
def break_scatter(bm, col, margin, window, brk_label, height):
    """Every game: margin at the break (across) against the final margin (up),
    W green / L red / draw grey, with the chosen position shaded."""
    fig = go.Figure()
    fig.add_vrect(x0=margin - window, x1=margin + window, fillcolor=COLORS["freo"],
                  opacity=0.10, line_width=0)
    for res, name, color in [("W", "Won", COLORS["win"]), ("L", "Lost", COLORS["loss"]),
                             ("D", "Drew", COLORS["neutral"])]:
        g = bm[bm["result"] == res]
        if not len(g):
            continue
        fig.add_trace(go.Scatter(
            x=g[col], y=g["margin"], mode="markers", name=name,
            marker=dict(size=9, color=color, line=dict(color="#FFFFFF", width=2)),
            customdata=list(zip(g["season"], g["round"], g["opponent"])),
            hovertemplate="%{customdata[0]} %{customdata[1]} v %{customdata[2]}<br>"
                          f"{brk_label}: " + "%{x:+d}<br>Final: %{y:+d}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=COLORS["muted"], width=1, dash="dot"))
    fig.add_vline(x=0, line=dict(color=COLORS["muted"], width=1, dash="dot"))
    fig = style_fig(fig, "Final margin", unified=False, height=height)
    fig.update_layout(margin=dict(l=8, r=12, t=24, b=8))
    fig.update_xaxes(title=dict(text=f"Margin at {brk_label.lower()}",
                                font=dict(color=COLORS["muted"], size=11)), showgrid=True,
                     gridcolor=COLORS["grid"], zeroline=False)
    return fig


# ---- Wharf-ai answer charts -------------------------------------------------------
def answer_chart(series, title, y_title, kind="line", height=210):
    """A small chart for the Wharf-ai panel. series: [(name, x list, y list)].
    Series colours follow a fixed order (Freo purple first)."""
    order = SERIES  # fixed order, never cycled
    fig = go.Figure()
    for i, (name, x, y) in enumerate(series):
        color = order[i % len(order)]
        if kind == "bar":
            fig.add_trace(go.Bar(y=x, x=y, name=name, orientation="h",
                                 marker=dict(color=color, cornerradius=3),
                                 text=[f"{v:.1f}" for v in y], textposition="outside",
                                 textfont=dict(size=10, color=COLORS["ink"]), cliponaxis=False,
                                 hovertemplate="%{y}: <b>%{x:.1f}</b><extra></extra>"))
        else:
            fig.add_trace(go.Scatter(x=x, y=y, name=name, mode="lines+markers",
                                     line=dict(color=color, width=2), marker=dict(size=6),
                                     hovertemplate=name + " %{x}: <b>%{y:.1f}</b><extra></extra>"))
    fig = style_fig(fig, y_title, unified=kind != "bar", height=height)
    fig.update_layout(title=dict(text=title, font=dict(size=12, color=COLORS["ink"]), x=0, y=0.98),
                      margin=dict(l=4, r=24, t=48 if len(series) > 1 else 30, b=4),
                      showlegend=len(series) > 1,
                      legend=dict(y=1.0, yanchor="bottom", font=dict(size=10)))
    if kind == "bar":
        fig.update_yaxes(autorange="reversed", tickfont=dict(size=10))
        fig.update_xaxes(showticklabels=False, showgrid=False)
    else:
        fig.update_xaxes(tickangle=-90, tickfont=dict(size=9))
    return fig


# ---- Opponent scout report ------------------------------------------------------
def rank_dumbbell(avg, ranks, team, stats, height, freo="Fremantle", team_color=None, focus=None):
    """League rank (18th on the left, 1st on the right) on each stat for the
    opponent (in its club colour) and Freo (purple), joined by a line. focus:
    (top 3 stats, bottom 3 stats) for the club, marked up and down in the labels."""
    team_color = team_color or COLORS["opp"]
    fig = go.Figure()
    labels = [l for l, _, _ in stats]
    for (label, col, _), y in zip(stats, labels):
        a, b = ranks.loc[team, col], ranks.loc[freo, col]
        fig.add_trace(go.Scatter(x=[a, b], y=[y, y], mode="lines", hoverinfo="skip",
                                 line=dict(color=COLORS["grid"], width=4), showlegend=False))
    for name, who, color in [(team, team, team_color), ("Fremantle", freo, COLORS["freo"])]:
        fig.add_trace(go.Scatter(
            x=[ranks.loc[who, c] for _, c, _ in stats], y=labels, mode="markers", name=name,
            marker=dict(size=11, color=color, line=dict(color="#FFFFFF", width=2)),
            customdata=[[avg.loc[who, c]] for _, c, _ in stats],
            hovertemplate=f"{name}<br>%{{y}}: %{{customdata[0]:.1f}} a game<br>"
                          "Rank %{x:.0f} of 18<extra></extra>"))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=8, t=22, b=4))
    fig.update_xaxes(range=[18.6, 0.4], tickvals=[18, 12, 6, 1],
                     ticktext=["18th", "12th", "6th", "1st"], showgrid=True, gridcolor=COLORS["grid"])
    top, low = focus if focus else ([], [])
    ticks = [f"<b>▲ {l}</b>" if l in top else f"<b>▼ {l}</b>" if l in low else l for l in labels]
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11), tickmode="array",
                     tickvals=labels, ticktext=ticks)
    return _inline_key(fig, [(team, team_color), ("Fremantle", COLORS["freo"])])


def _last_n_band(fig, n_points, n, label):
    """Shade the last n points of a category axis and label the stretch (the
    "last 5" a takeaway talks about)."""
    if n_points < n + 2:
        return
    fig.add_vrect(x0=n_points - n - 0.5, x1=n_points - 0.5, fillcolor=COLORS["freo"],
                  opacity=0.07, line_width=0, layer="below")
    # Above the plot area, so no bar or point ever covers it.
    fig.add_annotation(x=n_points - n - 0.5, y=1, xref="x", yref="paper", text=label,
                       showarrow=False, xanchor="left", yanchor="bottom", xshift=2,
                       font=dict(size=10, color=COLORS["ink"]))
    fig.update_layout(margin=dict(t=max(fig.layout.margin.t or 0, 16)))


def form_bars(games, height):
    """A club's margin in each of its recent games, green win / red loss, the last
    five shaded (the takeaway's "Last 5")."""
    colors = [{"W": COLORS["win"], "L": COLORS["loss"]}.get(r, COLORS["neutral"]) for r in games["result"]]
    x = (games["api_round"].str.replace("Round ", "R", regex=False)
         .str.replace(r"^(\w)\w* .*Finals?$", r"\1F", regex=True) + " " +
         games["opponent"].map(D.abbr)).tolist()
    fig = go.Figure(go.Bar(
        x=x, y=games["margin"], marker=dict(color=colors, cornerradius=3),
        customdata=games[["opponent", "score_for", "score_against"]].values,
        hovertemplate="%{x} v %{customdata[0]}<br>%{customdata[1]} to %{customdata[2]} "
                      "(%{y:+})<extra></extra>"))
    fig = style_fig(fig, "Margin", unified=False, height=height)
    fig.update_layout(showlegend=False, bargap=0.2, margin=dict(l=4, r=6, t=6, b=4))
    fig.update_xaxes(tickangle=-90, tickfont=dict(size=9))
    fig.update_yaxes(zeroline=True, zerolinecolor=COLORS["grid"])
    last = games.tail(5)
    w = int((last["result"] == "W").sum())
    _last_n_band(fig, len(games), 5, f"last 5: {w}-{len(last) - w}")
    return fig


# ---- Player profile ---------------------------------------------------------------
def player_trend(me, col, label, height):
    """One player's number in every game of the season, with the season
    average as a dashed line."""
    x = (me["round"] + " " + me["opponent"].map(D.abbr)).tolist()
    avg = me[col].mean()
    colors = [{"W": COLORS["win"], "L": COLORS["loss"]}.get(r, COLORS["neutral"]) for r in me["result"]]
    fig = go.Figure(go.Scatter(
        x=x, y=me[col], mode="lines+markers", line=dict(color=COLORS["freo"], width=2),
        marker=dict(size=8, color=colors, line=dict(color="#FFFFFF", width=2)),
        customdata=me[["opponent", "result", "margin"]].values,
        hovertemplate="%{x} v %{customdata[0]} (%{customdata[1]} %{customdata[2]:+})<br>"
                      + label + ": <b>%{y:.0f}</b><extra></extra>", showlegend=False))
    fig.add_hline(y=avg, line=dict(color=COLORS["muted"], width=1, dash="dash"),
                  annotation_text=f"season avg {avg:.1f}", annotation_position="top left",
                  annotation_font=dict(size=11, color=COLORS["muted"]))
    # The takeaway's last 5: shaded, with its own average drawn across just those games.
    n = len(me)
    if n >= 7:
        last5 = me[col].tail(5).mean()
        fig.add_trace(go.Scatter(x=x[-5:], y=[last5] * 5, mode="lines", hoverinfo="skip",
                                 line=dict(color=COLORS["freo"], width=2, dash="dot"),
                                 showlegend=False))
    # Best and lowest games, labelled on the point.
    if n >= 3 and me[col].max() > me[col].min():
        vals = me[col].tolist()
        for i, where, word in ((vals.index(max(vals)), "top center", "best"),
                               (vals.index(min(vals)), "bottom center", "low")):
            fig.add_annotation(x=x[i], y=vals[i], text=f"{word} {vals[i]:.0f}", showarrow=False,
                               yshift=12 if word == "best" else -12,
                               font=dict(size=10, color=COLORS["ink"]))
    fig = style_fig(fig, label, unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=8, t=14, b=4))
    if n >= 7:   # after style_fig, which resets the margins
        _last_n_band(fig, n, 5, f"last 5: {last5:.1f} a game")
    fig.update_xaxes(tickangle=-90, tickfont=dict(size=10))
    lo, hi = me[col].min(), me[col].max()
    pad = (hi - lo) * 0.18 or 2
    fig.update_yaxes(range=[lo - pad, hi + pad])
    return fig


def squad_rank_bars(pr, height, focus=None):
    """Squad rank on each stat as a bar (longer = better rank), value labelled.
    focus: the stats the takeaway names (1sts, or top 3s)."""
    score = pr["squad"] - pr["rank"] + 1
    alpha = _alpha(pr["stat"], focus)
    fig = go.Figure(go.Bar(
        y=pr["stat"], x=score, orientation="h",
        marker=dict(color=COLORS["freo"], cornerradius=3, opacity=alpha),
        text=[f"{int(r)}{'st' if r == 1 else 'nd' if r == 2 else 'rd' if r == 3 else 'th'} · {v:.1f}"
              for r, v in zip(pr["rank"], pr["value"])],
        textposition="outside", textfont=dict(size=11, color=_ink(alpha)), cliponaxis=False,
        customdata=pr[["rank", "squad", "value"]].values,
        hovertemplate="%{y}: %{customdata[2]:.1f} a game<br>Rank %{customdata[0]} of "
                      "%{customdata[1]} in the squad<extra></extra>"))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=70, t=4, b=4), bargap=0.3)
    fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, pr["squad"].max() + 0.5])
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=12), tickmode="array",
                     tickvals=list(pr["stat"]), ticktext=_bold(list(pr["stat"]), focus or []))
    return fig


PAIR = (COLORS["freo"], COLORS["opp"])   # player A, player B (validated pair, CVD dE 17)


def compare_trend(season_games, logs, names, col, label, height):
    """Two players' numbers game by game across the season (a gap where one
    didn't play), each with a dashed season average."""
    order = season_games.sort_values("game_dt")
    x = (order["round"] + " " + order["opponent"].map(D.abbr)).tolist()
    fig = go.Figure()
    for log, name, color in zip(logs, names, PAIR):
        by_round = log.set_index("round")[col]
        y = [by_round.get(r) for r in order["round"]]
        fig.add_trace(go.Scatter(
            x=x, y=y, name=name, mode="lines+markers", connectgaps=False,
            line=dict(color=color, width=2), marker=dict(size=8, color=color,
                                                         line=dict(color="#FFFFFF", width=2)),
            hovertemplate="%{x}<br>" + name + ": <b>%{y:.0f}</b> " + label.lower()
                          + "<extra></extra>"))
        avg = log[col].mean()
        if avg == avg:
            fig.add_hline(y=avg, line=dict(color=color, width=1, dash="dash"))
    fig = style_fig(fig, label, unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=8, t=10, b=4))
    fig.update_xaxes(tickangle=-90, tickfont=dict(size=10))
    return fig


def compare_ranks(cmp, names, height):
    """Squad rank on each stat for two players, joined by a line (1st on the
    right). Only stats where both have a rank."""
    c = cmp.dropna(subset=["rank_a", "rank_b"])
    c = c.head(max(6, int((height - 30) / 16))).iloc[::-1]   # as many as fit, 16px a row
    squad = int(c["squad"].max()) if len(c) else 1
    fig = go.Figure()
    for _, r in c.iterrows():
        fig.add_trace(go.Scatter(x=[r["rank_a"], r["rank_b"]], y=[r["stat"]] * 2, mode="lines",
                                 line=dict(color=COLORS["grid"], width=6), hoverinfo="skip",
                                 showlegend=False))
    for key, name, color in (("a", names[0], PAIR[0]), ("b", names[1], PAIR[1])):
        fig.add_trace(go.Scatter(
            x=c[f"rank_{key}"], y=c["stat"], mode="markers", name=name,
            marker=dict(size=11, color=color, line=dict(color="#FFFFFF", width=2)),
            customdata=c[[f"avg_{key}", "squad"]].values,
            hovertemplate="%{y}: " + name + " %{customdata[0]:.1f} a game, rank %{x} of "
                          "%{customdata[1]}<extra></extra>"))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=12, t=4, b=4))
    fig.update_xaxes(autorange=False, range=[squad + 0.5, 0.5], tickvals=[1, 5, 10, 15, 20, 25][: 1 + squad // 5],
                     ticktext=["1st", "5th", "10th", "15th", "20th", "25th"][: 1 + squad // 5],
                     tickfont=dict(size=10))
    fig.update_yaxes(tickfont=dict(size=11), showgrid=False, dtick=1)   # label every stat
    return fig
