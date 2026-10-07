"""Plotly charts for the Coach View. Sized for one 1440x900 screen: small
fixed heights, minimal chrome, detail on hover. One y axis only; a legend for
two or more series."""

import pandas as pd
import plotly.graph_objects as go
from theme import COLORS, DIVERGE, RAMP, SERIES, style_fig

import data as D

# Highlighting the finding: the marks a card's takeaway names keep full strength,
# the rest drop to this opacity (same hue, so identity never changes), and their
# labels go from ink to muted. focus=None draws every mark at full strength.
FADE = 0.4


def _round_ticks(fig, labels, max_n=11, size=10):
    """Horizontal x labels, the round only ("R2", "GF"; the opponent is on hover),
    thinned to about max_n so they never collide or need rotating. The last game
    is always shown (its neighbour is dropped if they'd touch)."""
    labels = list(labels)
    n = len(labels)
    step = max(1, -(-n // max_n))
    keep = [i for i in range(0, n, step)]
    if n and keep[-1] != n - 1:
        if n - 1 - keep[-1] < max(2, step // 2 + 1):
            keep.pop()
        keep.append(n - 1)
    fig.update_xaxes(tickangle=0, tickmode="array", tickvals=[labels[i] for i in keep],
                     ticktext=[str(labels[i]).split()[0] for i in keep], tickfont=dict(size=size))


def _end_labels(fig, x, items, height, lo, hi):
    """Direct labels at the right-hand end of lines, in place of a legend: items
    [(y, text)], nudged apart so they never overlap. Text in ink, never the
    series colour. The chart needs about 64px of right margin."""
    if not items:
        return
    gap = (hi - lo) / max(height - 40, 1) * 13      # one label line in data units
    ys = _spread(pd.Series([y for y, _ in items], index=range(len(items))), gap)
    for i, (_, text) in enumerate(items):
        fig.add_annotation(x=x, y=ys[i], text=text, showarrow=False, xanchor="left", xshift=8,
                           font=dict(size=10, color=COLORS["ink"]))


def _tag_pair(fig, y, a, text_a, b, text_b, reversed_x=False):
    """Name a dumbbell row's two dots just above them (the top row, in place of a
    colour key): the left dot's label runs left, the right dot's runs right."""
    a_left = (a > b) if reversed_x else (a <= b)
    for v, text, left in ((a, text_a, a_left), (b, text_b, not a_left)):
        fig.add_annotation(x=v, y=y, text=text, showarrow=False, yanchor="bottom", yshift=5,
                           xanchor="right" if left else "left", xshift=5 if left else -5,
                           font=dict(size=10, color=COLORS["ink"]))


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
    tags = ["Freo" if names[0] == "Fremantle" else D.abbr(names[0]),
            "Opp" if names[1] in ("Opposition", "Opponents") else D.abbr(names[1])]
    named = best if best is not None else qp["quarter"].iloc[0]   # the bars that carry the names
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
    # The named quarter's two bars carry the team names, in place of a colour key
    # (grouped bars sit 0.17 either side of the quarter's centre).
    k = list(qp["quarter"]).index(named)
    row = qp.iloc[k]
    for off, col, tag in ((-0.17, "freo", tags[0]), (0.17, "opp", tags[1])):
        fig.add_annotation(x=k + off, y=row[col] / 2, text=tag, showarrow=False, textangle=0,
                           font=dict(size=9, color="#FFFFFF"))
    if best is not None:
        fig.update_xaxes(tickmode="array", tickvals=list(qp["quarter"]),
                         ticktext=_bold(list(qp["quarter"]), best))
    return fig


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
    fig.update_xaxes(title=None, tickfont=dict(size=10))
    fig.update_yaxes(title=None, autorange="reversed", showgrid=False, tickfont=dict(size=12),
                     tickmode="array", tickvals=order, ticktext=_bold(order, focus or []))
    if order:
        top = order[0]
        _tag_pair(fig, top, avgs[top], "season", last3[top], "last 3")
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
    fig.update_xaxes(showgrid=False, showticklabels=show_x)
    if show_x:
        _round_ticks(fig, labels)
    fig.update_yaxes(showgrid=False, tickfont=dict(size=11),
                     categoryorder="array", categoryarray=["Result"] + rows,
                     tickmode="array", tickvals=["Result"] + rows,
                     ticktext=_bold(["Result"] + rows, focus if focus is not None else []))
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
        if strong and r["stat"] != stats[0]:   # the focus rates (on the top row the takeaway has them)
            for v in (r["behind_winrate"], r["ahead_winrate"]):
                fig.add_annotation(x=v, y=r["stat"], text=f"{v:.0f}%", showarrow=False,
                                   yanchor="bottom", yshift=5,
                                   font=dict(size=10, color=COLORS["ink"]))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=36, t=16, b=4))  # r: the swing column
    fig.update_xaxes(range=[-6, 106], tickvals=[0, 50, 100], ticktext=["0%", "50%", "100%"],
                     tickfont=dict(size=10))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=11), tickmode="array",
                     tickvals=stats, ticktext=_bold(stats, focus if focus is not None else []))
    fig.add_annotation(x=1, xref="paper", y=1, yref="paper", text="swing", showarrow=False,
                       xanchor="left", xshift=4, yanchor="bottom",
                       font=dict(size=10, color=COLORS["muted"]))
    # The top row's two dots say what they are, in place of a colour key (with the
    # focus rates when the top row is the focus).
    if len(wc):
        r = wc.iloc[0]
        short = lambda n: n.replace(" won it", "").replace("Their opponent", "opp")  # noqa: E731
        tags = {"behind": short(names[1]), "ahead": short(names[0])}
        for key in ("behind", "ahead"):   # a short name centred over each dot (rates: the takeaway)
            fig.add_annotation(x=r[f"{key}_winrate"], y=r["stat"], showarrow=False, yanchor="bottom",
                               yshift=5, text=tags[key], font=dict(size=10, color=COLORS["ink"]))
    return fig


def driver_multiples(panels, height, cols=2, focus=None):
    """What drives our margin as small multiples (after Tufte): one tiny scatter
    per stat, every game's differential (across, its own scale) against the final
    margin (up, the same scale in every panel), strongest relationship first, each
    titled with its stat and r. No ticks, just a faint zero line, so the shape is
    what reads. focus: the takeaway's stat, in purple; the rest in grey. Clicking a
    panel's dot opens that stat (curve_number is the panel's position in panels).
    panels: [(stat, pts, fit)] from data.driver_points."""
    from plotly.subplots import make_subplots
    n = len(panels)
    rows = -(-n // cols)
    titles = [f"<b>{st}</b> {fit['r']:+.2f}" if st == focus else f"{st} {fit['r']:+.2f}"
              for st, _, fit in panels]
    fig = make_subplots(rows=rows, cols=cols, shared_yaxes=True, horizontal_spacing=0.08,
                        vertical_spacing=min(0.22, 24 / max(height, 1) * rows / max(rows - 1, 1) * 0.9),
                        subplot_titles=titles)
    margins = [m for _, pts, _ in panels for m in pts["margin"]]
    lo, hi = min(margins), max(margins)
    pad = (hi - lo) * 0.08
    for i, (stat, pts, fit) in enumerate(panels):
        r, c = i // cols + 1, i % cols + 1
        strong = focus is None or stat == focus
        fig.add_trace(go.Scatter(
            x=pts["diff"], y=pts["margin"], mode="markers", showlegend=False,
            marker=dict(size=4, color=COLORS["freo"] if strong else COLORS["muted"],
                        opacity=0.85 if strong else 0.55),
            customdata=pts[["label", "opponent"]].values,
            hovertemplate="<b>%{customdata[0]}</b> v %{customdata[1]}<br>" + stat
                          + " diff %{x:+,.0f} · margin %{y:+d}<br>Click for every game<extra></extra>"),
            row=r, col=c)
        fig.add_hline(y=0, line=dict(color=COLORS["grid"], width=1), row=r, col=c)
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=4, t=18, b=2))
    fig.update_xaxes(showticklabels=False, fixedrange=True)
    fig.update_yaxes(showticklabels=False, fixedrange=True, range=[lo - pad, hi + pad])
    for ann in fig.layout.annotations:   # the panel titles
        ann.font = dict(size=10, color=COLORS["ink"])
        ann.yshift = -2
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
                     zeroline=False)
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
    fig.update_layout(showlegend=False, margin=dict(l=4, r=56, t=14, b=4))
    lo, hi = float(rm[qs].min().min()), float(rm[qs].max().max())
    pad = (hi - lo) * 0.18 or 5
    fig.update_yaxes(range=[min(lo, 0) - pad, max(hi, 0) + pad])
    _end_labels(fig, "Q4", [(float(rm.loc[r, "Q4"]), lbl) for r, lbl in (("W", "wins"), ("L", "losses"))
                            if r in rm.index], height, min(lo, 0) - pad, max(hi, 0) + pad)
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
    fig.update_xaxes(title=dict(text=xlab + " per game", font=dict(color=COLORS["muted"], size=11)))
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
    fig.update_layout(showlegend=False, margin=dict(l=4, r=64, t=14, b=4))
    lo = min(min(y), float(avg.min().min()) if len(avg) else 0,
             float(others.min().min()) if len(others) else 0)
    hi = max(max(y), float(avg.max().max()) if len(avg) else 0,
             float(others.max().max()) if len(others) else 0)
    pad = (hi - lo) * 0.15 or 5
    fig.update_yaxes(range=[lo - pad, hi + pad])
    # Each line named at its end, in place of a colour key.
    ends = [(y[-1], "this game")] + [(float(avg.loc[r, "Q4"]), lbl) for r, lbl in
                                     (("W", "avg win"), ("L", "avg loss")) if r in avg.index]
    _end_labels(fig, "Q4", ends, height, lo - pad, hi + pad)
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


def player_ranges(log, stats, height):
    """One player's season, stat by stat: every game a small dot placed by that
    game as a % of his own season average (the centre line), the latest game a
    ringed dot with its number, each stat's lowest-highest at the right. Clicking
    a dot opens that game. stats: [(label, column)]; log in date order."""
    labels = [lbl for lbl, _ in stats]
    games = (log["round"] + " v " + log["opponent"].map(D.abbr)).tolist()
    fig = go.Figure()
    xs, ys, cd = [], [], []
    for lbl, col in stats:
        v = log[col]
        avg = v.mean()
        p = (v / max(avg, 0.1) * 100).clip(5, 205)
        xs += p.tolist()
        ys += [lbl] * len(v)
        cd += [[g, val, avg, r, rnd] for g, val, r, rnd in
               zip(games, v, log["result"], log["round"])]
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", showlegend=False,
        marker=dict(size=8, color=RAMP[1], opacity=0.75, line=dict(color="#FFFFFF", width=1)),
        customdata=cd,
        hovertemplate="<b>%{customdata[0]}</b> (%{customdata[3]})<br>%{y}: %{customdata[1]:.0f}"
                      " (season avg %{customdata[2]:.1f})<br>Click to open this game<extra></extra>"))
    last = log.iloc[-1]
    lx = [min(max(last[col] / max(log[col].mean(), 0.1) * 100, 5), 205) for _, col in stats]
    fig.add_trace(go.Scatter(
        x=lx, y=labels, mode="markers+text", showlegend=False, hoverinfo="skip",
        text=[f"{last[col]:.0f}" for _, col in stats], textposition="top center",
        textfont=dict(size=10, color=COLORS["ink"]),
        marker=dict(size=12, color=COLORS["freo"], line=dict(color="#FFFFFF", width=2))))
    for lbl, col in stats:
        fig.add_annotation(x=1, xref="paper", y=lbl, xanchor="left", xshift=8, showarrow=False,
                           text=f"{log[col].min():.0f}–{log[col].max():.0f}",
                           font=dict(size=10, color=COLORS["muted"]))
    fig.add_vline(x=100, line=dict(color=COLORS["muted"], width=1))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=56, t=26, b=4))   # t: the top row's latest number
    fig.add_annotation(x=1, xref="paper", y=1, yref="paper", text="range", showarrow=False,
                       xanchor="left", xshift=8, yanchor="bottom",
                       font=dict(size=10, color=COLORS["muted"]))
    fig.update_xaxes(range=[0, 210], tickvals=[0, 50, 100, 150, 200],
                     ticktext=["0", "half", "his avg", "1.5x", "2x"],
                     tickfont=dict(size=10, color=COLORS["muted"]),
                     fixedrange=True)
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11), fixedrange=True)
    return fig


# Below this season average a stat is too small for a % to mean much (two tackles
# instead of one is "200%"): those players get no standout label on it.
VS_SELF_MIN_AVG = {"disposals": 5, "contested_poss": 2, "metres_gained": 60, "tackles": 1.5,
                   "pressure_acts": 6, "score_involvements": 1.5, "marks": 1.5,
                   "clearances": 1, "inside_50s": 1.5, "goals": 1.5, "rating_points": 6}


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
                                font=dict(color=COLORS["muted"], size=11)), zeroline=False)
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
        _round_ticks(fig, series[0][1] if series else [], max_n=8, size=9)
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
                     ticktext=["18th", "12th", "6th", "1st"])
    top, low = focus if focus else ([], [])
    ticks = [f"<b>▲ {l}</b>" if l in top else f"<b>▼ {l}</b>" if l in low else l for l in labels]
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11), tickmode="array",
                     tickvals=labels, ticktext=ticks)
    fig.update_layout(margin=dict(t=16))
    col0 = stats[0][1]
    _tag_pair(fig, labels[0], ranks.loc[team, col0], D.abbr(team), ranks.loc[freo, col0], "Freo",
              reversed_x=True)
    return fig


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
    _round_ticks(fig, x, size=9)
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
    _round_ticks(fig, x)
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
    fig.update_layout(showlegend=False, margin=dict(l=4, r=70, t=10, b=4))
    _round_ticks(fig, x)
    ends = []
    for log, name in zip(logs, names):
        if len(log):
            ends.append((float(log.sort_values("game_dt")[col].iloc[-1]), name.split()[-1]))
    vals = [v for log in logs for v in log[col].dropna()]
    if vals:
        _end_labels(fig, x[-1], ends, height, min(vals), max(vals))
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
    fig.update_layout(showlegend=False, margin=dict(l=4, r=12, t=16, b=4))
    fig.update_xaxes(autorange=False, range=[squad + 0.5, 0.5], tickvals=[1, 5, 10, 15, 20, 25][: 1 + squad // 5],
                     ticktext=["1st", "5th", "10th", "15th", "20th", "25th"][: 1 + squad // 5],
                     tickfont=dict(size=10))
    fig.update_yaxes(tickfont=dict(size=11), showgrid=False, dtick=1)   # label every stat
    if len(c):   # the top row (the last one drawn) names the two players
        top = c.iloc[-1]
        _tag_pair(fig, top["stat"], top["rank_a"], names[0].split()[-1], top["rank_b"],
                  names[1].split()[-1], reversed_x=True)
    return fig


# ---- Demo (simulated): the ground, positions and running --------------------------
# Only for the ?demo=1 view (sim.py). Every figure here carries a SIMULATED watermark.
GROUND_LINE = "#C4C4C4"
EVENT_COLORS = {"Goals": COLORS["series3"], "Marks": COLORS["series4"],
                "Contested": COLORS["freo"], "Uncontested": COLORS["opp"]}


def _arc(cx, r, side):
    """The 50 m arc around a goal, the part inside the oval, as an SVG path."""
    import math
    pts = []
    for k in range(121):
        a = math.radians(90 + 180 * k / 120) if side > 0 else math.radians(-90 + 180 * k / 120)
        x, y = cx + r * math.cos(a), r * math.sin(a)
        if (x / 82) ** 2 + (y / 66) ** 2 <= 1.0005:
            pts.append((x, y))
    return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in pts)


def ground(fig, height, attack="Freo"):
    """Draw an AFL ground to scale (the side named attack kicks to the right) and
    size the axes."""
    # The turf below everything; the markings above the data, so they always show.
    line = dict(color="rgba(120,120,120,0.55)", width=1.1)
    fig.add_shape(type="circle", x0=-82, x1=82, y0=-66, y1=66, line=dict(width=0),
                  fillcolor="#FBFBF8", layer="below")
    fig.add_shape(type="circle", x0=-82, x1=82, y0=-66, y1=66,
                  line=dict(color="rgba(120,120,120,0.7)", width=1.5), layer="above")
    fig.add_shape(type="rect", x0=-25, x1=25, y0=-25, y1=25, line=line, layer="above")
    for r in (3, 10):
        fig.add_shape(type="circle", x0=-r, x1=r, y0=-r, y1=r, line=line, layer="above")
    for side in (1, -1):
        gx = 82 * side
        fig.add_shape(type="path", path=_arc(gx, 50, side), line=line, layer="above")
        fig.add_shape(type="rect", x0=gx - 9 * side, x1=gx, y0=-3.2, y1=3.2, line=line, layer="above")
        for py in (-9.6, -3.2, 3.2, 9.6):
            fig.add_shape(type="line", x0=gx, x1=gx + 2 * side, y0=py, y1=py, line=line, layer="above")
    # Plainly simulated, wherever this picture ends up.
    fig.add_annotation(x=0, xref="paper", y=0, yref="paper", text="<b>SIMULATED</b>", showarrow=False,
                       xanchor="left", yanchor="bottom", bgcolor="#E8A33D", borderpad=3,
                       font=dict(size=10, color="#1A1A1A"))
    fig.add_annotation(x=1, xref="paper", y=1, yref="paper", text=f"{attack} attack →", showarrow=False,
                       xanchor="right", yanchor="bottom", font=dict(size=10, color=COLORS["muted"]))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=4, t=16, b=4), showlegend=False)
    fig.update_xaxes(range=[-86, 86], showticklabels=False, fixedrange=True)
    fig.update_yaxes(range=[-70, 70], showticklabels=False, fixedrange=True,
                     scaleanchor="x", scaleratio=1)
    return fig


def ground_heat(xy, height, attack="Freo"):
    """Where the player (or team) spent the game: a smoothed density on a 2 m
    grid, light to dark purple, clipped to the oval and clear where there's
    little time."""
    import numpy as np
    xs, ys = np.arange(-82, 82.5, 1.5), np.arange(-66, 66.5, 1.5)
    h, _, _ = np.histogram2d(xy[:, 1], xy[:, 0], bins=[np.append(ys - 1, ys[-1] + 1),
                                                        np.append(xs - 1, xs[-1] + 1)])
    k = np.exp(-0.5 * (np.arange(-8, 9) / 3.4) ** 2)
    k /= k.sum()
    h = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), 1, h)
    h = np.apply_along_axis(lambda c: np.convolve(c, k, mode="same"), 0, h)
    h = h / (h.max() or 1)
    gx, gy = np.meshgrid(xs, ys)
    h[((gx / 82) ** 2 + (gy / 66) ** 2 > 1) | (h < 0.08)] = np.nan   # outside the oval, or barely
    scale = [[i / (len(RAMP) - 1), c] for i, c in enumerate(RAMP)]
    fig = go.Figure(go.Heatmap(z=h, x=xs, y=ys, colorscale=scale, zmin=0.08, zmax=1,
                               showscale=False, opacity=0.9, hoverinfo="skip", zsmooth="best"))
    return ground(fig, height, attack)


def ground_events(layers, height, attack="Freo"):
    """Real counts at simulated spots: {layer: (array of (x, y), hover labels)}, a
    colour per layer from the validated series order, labelled in the key above."""
    fig = go.Figure()
    for name, (xy, hover) in layers.items():
        if not len(xy):
            continue
        fig.add_trace(go.Scatter(
            x=xy[:, 0], y=xy[:, 1], mode="markers", name=name,
            marker=dict(size=9 if name == "Goals" else 7, color=EVENT_COLORS[name],
                        symbol="star" if name == "Goals" else "circle", opacity=0.85,
                        line=dict(color="#FFFFFF", width=1)),
            text=hover, hovertemplate="%{text}<br>(simulated spot)<extra>" + name + "</extra>"))
    fig = ground(fig, height, attack)
    shown = [(n, EVENT_COLORS[n]) for n, (xy, _) in layers.items() if len(xy)]
    return _inline_key(fig, shown) if shown else fig


def running_trend(run, height):
    """One player's simulated distance in each game, his average dashed; the
    hover has high-speed metres, sprints and top speed."""
    x = (run["round"] + " " + run["opponent"].map(D.abbr)).tolist()
    avg = run["distance_km"].mean()
    fig = go.Figure(go.Bar(
        x=x, y=run["distance_km"], marker=dict(color=RAMP[3] if len(RAMP) > 3 else COLORS["freo"],
                                               cornerradius=2),
        customdata=run[["hsr_m", "sprints", "top_speed"]].values,
        hovertemplate="%{x}<br><b>%{y:.1f} km</b> · %{customdata[0]:,} m high speed · "
                      "%{customdata[1]} sprints · top %{customdata[2]:.1f} km/h"
                      "<br>(simulated)<extra></extra>"))
    fig.add_hline(y=avg, line=dict(color=COLORS["muted"], width=1, dash="dash"),
                  annotation_text=f"avg {avg:.1f} km", annotation_position="top left",
                  annotation_font=dict(size=10, color=COLORS["muted"]))
    fig = style_fig(fig, "Distance (km, simulated)", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=8, t=10, b=4), bargap=0.25)
    _round_ticks(fig, x)
    lo = run["distance_km"].min()
    fig.update_yaxes(range=[max(0, lo * 0.8), run["distance_km"].max() * 1.08])
    return fig


def running_quarters(by_q, height):
    """Simulated distance per player in each quarter, wins against losses: the
    late-game fade. by_q: rows W / L, columns q1_km..q4_km."""
    qs = ["Q1", "Q2", "Q3", "Q4"]
    fig = go.Figure()
    ends = []
    for res, name, color in (("W", "wins", COLORS["win"]), ("L", "losses", COLORS["loss"])):
        if res not in by_q.index:
            continue
        y = [by_q.loc[res, f"q{i}_km"] for i in range(1, 5)]
        fig.add_trace(go.Scatter(x=qs, y=y, mode="lines+markers", name=name,
                                 line=dict(color=color, width=2), marker=dict(size=7),
                                 hovertemplate=name + " %{x}: %{y:.2f} km a player<br>(simulated)"
                                               "<extra></extra>"))
        ends.append((y[-1], name))
    fig = style_fig(fig, "km a player (simulated)", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=56, t=10, b=4))
    vals = by_q.values.ravel()
    if len(vals):
        _end_labels(fig, "Q4", ends, height, float(vals.min()), float(vals.max()))
    return fig
