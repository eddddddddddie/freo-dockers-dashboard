"""Plotly charts for the Coach View. Sized for one 1440x900 screen: small
fixed heights, minimal chrome, detail on hover. One y axis only; a legend for
two or more series."""

import plotly.graph_objects as go
from theme import COLORS, style_fig

import data as D


def margin_bars(tdf, height):
    """Margin in every game of the season, coloured by result."""
    labels = D.game_labels(tdf)
    colors = [COLORS["win"] if r == "W" else COLORS["loss"] for r in tdf["result"]]
    avg = tdf["margin"].mean()
    fig = go.Figure(go.Bar(
        x=labels, y=tdf["margin"], marker=dict(color=colors, cornerradius=3),
        customdata=tdf[["opponent", "result", "freo_score", "opp_score", "venue"]].values,
        hovertemplate="<b>%{x}</b> vs %{customdata[0]}<br>%{customdata[1]} "
                      "%{customdata[2]} to %{customdata[3]} (%{y:+})<br>"
                      "%{customdata[4]}<extra></extra>",
    ))
    fig.add_hline(y=avg, line=dict(color=COLORS["muted"], width=1, dash="dot"))
    fig = style_fig(fig, "Margin", unified=False, height=height)
    fig.update_layout(bargap=0.18, showlegend=False)
    fig.update_xaxes(tickangle=-90, tickfont=dict(size=10))
    fig.update_yaxes(zeroline=True, zerolinecolor=COLORS["grid"])
    return fig


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
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08,
                      margin=dict(l=4, r=4, t=26, b=4))
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
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.06)
    top = max(qp["freo"].max(), qp["opp"].max())
    fig.update_yaxes(range=[0, top * 1.22])
    return fig


def form_heatmap(vals, avgs, stat_label, height):
    """Player form: each cell is the player's number in that game, coloured by
    how far it sits above (blue) or below (red) their own season average."""
    dev = vals.sub(avgs, axis=0)
    lim = max(float(dev.abs().max().max() or 1), 1.0)
    rows = [f"{p}  ({a:.1f})" for p, a in avgs.items()]
    text = vals.map(lambda v: "" if v != v else f"{v:.0f}").values
    fig = go.Figure(go.Heatmap(
        z=dev.values, x=list(vals.columns), y=rows, text=text,
        texttemplate="%{text}", textfont=dict(size=11),
        colorscale=[[0, "#C53030"], [0.5, "#F0EFEC"], [1, "#2B6CB0"]],
        zmin=-lim, zmax=lim, xgap=2, ygap=2, showscale=False,
        customdata=vals.values,
        hovertemplate="%{y}<br>%{x}: <b>%{customdata:.0f}</b> " + stat_label.lower() +
                      "<br>%{z:+.1f} vs season avg<extra></extra>",
        hoverongaps=False,
    ))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(margin=dict(l=4, r=4, t=4, b=4))
    fig.update_xaxes(side="top", tickfont=dict(size=10))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=11))
    return fig


def goalkickers_bar(gk, height):
    fig = go.Figure(go.Bar(
        y=gk.index, x=gk["goals"], orientation="h",
        marker=dict(color=COLORS["freo"], cornerradius=3),
        text=gk["goals"], textposition="outside",
        textfont=dict(size=11, color=COLORS["ink"]),
        customdata=gk["games"],
        hovertemplate="%{y}: <b>%{x}</b> goals in %{customdata} games<extra></extra>",
    ))
    fig = style_fig(fig, "", unified=False, height=height)
    fig.update_layout(showlegend=False, margin=dict(l=4, r=4, t=4, b=4))
    fig.update_xaxes(showticklabels=False, showgrid=False,
                     range=[0, gk["goals"].max() * 1.2 if len(gk) else 1])
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11))
    return fig
