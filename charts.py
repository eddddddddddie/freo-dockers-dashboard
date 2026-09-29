"""Reusable Plotly charts. Every chart ships a legend (for two or more series),
a hover layer, and a table view alongside it in the page. One y axis only."""

import plotly.graph_objects as go
from theme import COLORS, style_fig


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
