"""Reusable Plotly charts. Every chart ships a legend (for two or more series),
a hover layer, and a table view alongside it in the page. One y axis only."""

import plotly.graph_objects as go
from theme import COLORS, style_fig, FONT


def _customdata(tdf):
    return tdf[["opponent", "result", "margin"]].values


def freo_vs_opp_line(tdf, freo_col, opp_col, y_title,
                     freo_name="Fremantle", opp_name="Opposition"):
    cd = _customdata(tdf)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tdf["round"], y=tdf[freo_col], name=freo_name, mode="lines+markers",
        line=dict(color=COLORS["freo"], width=2), marker=dict(size=8),
        customdata=cd,
        hovertemplate="%{x} vs %{customdata[0]}<br>" + freo_name +
        ": <b>%{y}</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=tdf["round"], y=tdf[opp_col], name=opp_name, mode="lines+markers",
        line=dict(color=COLORS["opp"], width=2), marker=dict(size=8),
        hovertemplate=opp_name + ": <b>%{y}</b><extra></extra>",
    ))
    return style_fig(fig, y_title)


def single_line(tdf, col, y_title, name, color_key="freo"):
    cd = _customdata(tdf)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tdf["round"], y=tdf[col], name=name, mode="lines+markers",
        line=dict(color=COLORS[color_key], width=2), marker=dict(size=8),
        customdata=cd,
        hovertemplate="%{x} vs %{customdata[0]}<br>" + name +
        ": <b>%{y}</b> (%{customdata[1]} by %{customdata[2]})<extra></extra>",
    ))
    return style_fig(fig, y_title)


def goals_behinds_bar(tdf):
    """Team goals and behinds per game, stacked. Team totals include rushed
    behinds, so this is the correct base for goal accuracy."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=tdf["round"], y=tdf["freo_goals"], name="Goals",
        marker=dict(color=COLORS["freo"], line=dict(color="white", width=1)),
        hovertemplate="%{x}<br>Goals: <b>%{y}</b><extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=tdf["round"], y=tdf["freo_behinds"], name="Behinds",
        marker=dict(color=COLORS["teal"], line=dict(color="white", width=1)),
        hovertemplate="Behinds: <b>%{y}</b><extra></extra>",
    ))
    fig.update_layout(barmode="stack", bargap=0.28)
    return style_fig(fig, "Scoring shots")


def result_score_bar(tdf):
    """Freo score per game, coloured by result (win green, loss red)."""
    colors = [COLORS["win"] if r == "W" else COLORS["loss"] for r in tdf["result"]]
    cd = tdf[["opponent", "result", "opp_score"]].values
    fig = go.Figure(go.Bar(
        x=tdf["round"], y=tdf["freo_score"],
        marker=dict(color=colors, line=dict(color="white", width=1)),
        customdata=cd,
        hovertemplate="%{x} vs %{customdata[0]}<br>Freo <b>%{y}</b> "
        "to %{customdata[2]} (%{customdata[1]})<extra></extra>",
    ))
    fig.update_layout(bargap=0.28)
    return style_fig(fig, "Freo score", unified=False)


def player_form(pdf_player, col, y_title, season_avg, last5_avg):
    """A player's game by game values with season and last-5 reference lines."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pdf_player["round"], y=pdf_player[col], name=y_title,
        mode="lines+markers",
        line=dict(color=COLORS["freo"], width=2), marker=dict(size=8),
        customdata=pdf_player[["opponent", "result"]].values,
        hovertemplate="%{x} vs %{customdata[0]}<br>" + y_title +
        ": <b>%{y}</b> (%{customdata[1]})<extra></extra>",
    ))
    fig.add_hline(y=season_avg, line=dict(color=COLORS["muted"], width=1.5, dash="dash"),
                  annotation_text=f"Season avg {season_avg:.1f}",
                  annotation_position="top left",
                  annotation_font=dict(color=COLORS["muted"], size=11))
    fig.add_hline(y=last5_avg, line=dict(color=COLORS["magenta"], width=1.5, dash="dot"),
                  annotation_text=f"Last 5 {last5_avg:.1f}",
                  annotation_position="bottom left",
                  annotation_font=dict(color=COLORS["magenta"], size=11))
    return style_fig(fig, y_title, unified=False)


def top_scorers_bar(gk):
    """Horizontal bar of leading goalkickers (Series indexed by player)."""
    s = gk[::-1]
    fig = go.Figure(go.Bar(
        x=s.values, y=s.index, orientation="h",
        marker=dict(color=COLORS["freo"], line=dict(color="white", width=1)),
        text=[int(v) for v in s.values], textposition="outside",
        hovertemplate="%{y}: <b>%{x}</b> goals<extra></extra>",
    ))
    fig = style_fig(fig, "", unified=False, height=max(210, 32 * len(s) + 40))
    top = float(s.max()) if len(s) else 1
    fig.update_xaxes(visible=False, range=[0, top * 1.18])  # headroom for outside labels
    fig.update_layout(margin=dict(l=8, r=16, t=6, b=6))
    return fig


def possession_donut(contested, uncontested):
    """Donut of contested vs uncontested possessions with the total in the centre."""
    total = contested + uncontested
    fig = go.Figure(go.Pie(
        values=[contested, uncontested], labels=["Contested", "Uncontested"],
        hole=0.62, sort=False, direction="clockwise",
        marker=dict(colors=[COLORS["freo"], COLORS["teal"]],
                    line=dict(color="white", width=2)),
        textinfo="percent", textfont=dict(color="white", size=13),
        hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white",
        font=dict(family=FONT, color=COLORS["ink"], size=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=6, r=6, t=6, b=6), height=260, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="center", x=0.5,
                    font=dict(color=COLORS["muted"], size=11)),
        annotations=[dict(
            text=f"<b>{total:,}</b><br><span style='font-size:11px;color:#6B7280'>possessions</span>",
            x=0.5, y=0.5, font=dict(size=22, color=COLORS["brand"]), showarrow=False)],
    )
    return fig


def trend_area(tdf, freo_col, opp_col, y_title):
    """Filled area trend of Freo vs opposition across the season."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tdf["round"], y=tdf[opp_col], name="Opposition", mode="lines",
        line=dict(color=COLORS["opp"], width=2), fill="tozeroy",
        fillcolor=COLORS["opp_fill"],
        hovertemplate="Opposition: <b>%{y}</b><extra></extra>"))
    fig.add_trace(go.Scatter(
        x=tdf["round"], y=tdf[freo_col], name="Fremantle", mode="lines+markers",
        line=dict(color=COLORS["freo"], width=2.5), marker=dict(size=6),
        fill="tozeroy", fillcolor=COLORS["freo_fill"],
        customdata=tdf[["opponent"]].values,
        hovertemplate="%{x} vs %{customdata[0]}<br>Fremantle: <b>%{y}</b><extra></extra>"))
    return style_fig(fig, y_title, height=300)


def volume_efficiency_scatter(tdf, xcol, ycol, xlab, ylab):
    """Per-game scatter (volume vs output) coloured by result, with mean quadrant
    lines. The dashboard's box-score answer to a chance-creation view."""
    colors = [COLORS["win"] if r == "W" else COLORS["loss"] for r in tdf["result"]]
    cd = tdf[["round", "opponent", "result"]].values
    fig = go.Figure(go.Scatter(
        x=tdf[xcol], y=tdf[ycol], mode="markers",
        marker=dict(color=colors, size=12, line=dict(color="white", width=1.5)),
        customdata=cd,
        hovertemplate="%{customdata[0]} vs %{customdata[1]} (%{customdata[2]})<br>"
        + xlab + ": <b>%{x}</b><br>" + ylab + ": <b>%{y}</b><extra></extra>"))
    fig.add_vline(x=tdf[xcol].mean(), line=dict(color=COLORS["grid"], width=1, dash="dash"))
    fig.add_hline(y=tdf[ycol].mean(), line=dict(color=COLORS["grid"], width=1, dash="dash"))
    fig = style_fig(fig, ylab, unified=False, height=300)
    fig.update_xaxes(title=dict(text=xlab, font=dict(color=COLORS["muted"], size=12)),
                     showgrid=True)
    return fig


def leader_counts_bar(counts, color_key="freo", top_n=10):
    """Horizontal bar of games led per player for one role."""
    s = counts.head(top_n)[::-1]
    fig = go.Figure(go.Bar(
        x=s.values, y=s.index, orientation="h",
        marker=dict(color=COLORS[color_key], line=dict(color="white", width=1)),
        text=[int(v) for v in s.values], textposition="outside",
        hovertemplate="%{y}: <b>%{x}</b> games led<extra></extra>",
    ))
    fig = style_fig(fig, "", unified=False, height=max(260, 34 * len(s) + 60))
    fig.update_xaxes(showgrid=True, title="Games led")
    return fig
