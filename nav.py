"""Navigation between views, and the view kept in the web address.

The address holds season, view, game (round label, e.g. GF), opp (club),
player and vs (the player compared with), e.g. ?season=2026&view=Match&game=GF, so a view can be bookmarked or
sent, and the browser's Back and Forward buttons move between views (the
viewport component reruns the app on popstate).

Streamlit won't let a control's value change after the control is drawn in
the same run, so a click that moves to another view queues the move
(`go`) and reruns; `apply_pending` sets the controls at the top of the next
run, before any are drawn.
"""

from urllib.parse import parse_qsl

import streamlit as st

VIEWS = ["Season", "Match", "Player", "Scout"]
# Picker options for the page across all of a view's options (kept in the
# address like any other pick: player=Whole squad, opp=All clubs, game=QT).
SQUAD, ALL_CLUBS, QT = "Whole squad", "All clubs", "Quarter-time check"
QT_ROUND = "QT"
MOM, MOM_ROUND = "Season momentum", "MOM"      # game=MOM: runs and momentum across the season


def go(**state):
    """Move to another view: go(view="Match", season=2026, game="GF")."""
    st.session_state["pending_nav"] = state
    st.rerun()


def _apply(state, seasons, game_label, players, clubs, from_url=False):
    season = state.get("season")
    if season is not None:
        try:
            season = int(season)
        except (TypeError, ValueError):
            season = None
    if season in seasons:
        st.session_state["season"] = season
    season = st.session_state.get("season", seasons[-1])
    view = state.get("view")
    if view in VIEWS:
        st.session_state["view"] = view
    if state.get("game"):
        label = game_label(season, str(state["game"]))
        if label:
            st.session_state[f"game_{season}"] = label
    if state.get("player") in players(season):
        st.session_state["player_pick"] = state["player"]
        # "vs": the player compared with; a move to a player without one clears it.
        st.session_state["player_vs"] = state["vs"] if state.get("vs") in players(season) else None
    if state.get("opp") in clubs():
        st.session_state["scout_team"] = state["opp"]
    # The games slice: a click elsewhere keeps the one picked; an address (a link,
    # Back/Forward) sets it, no "games" meaning all games.
    import data as D
    if state.get("games") in D.GAME_SLICES:
        st.session_state["games_slice"] = state["games"]
    elif from_url and view in ("Season", "Player"):
        st.session_state["games_slice"] = D.GAME_SLICES[0]


def apply_pending(seasons, game_label, players, clubs):
    """Before any control is drawn: apply a queued move, or on a visit's first
    run, the state in the web address. game_label(season, round) returns the
    game picker's label for a round; players(season) and clubs() list the
    valid names."""
    pending = st.session_state.pop("pending_nav", None)
    back = _back_forward()
    if pending:
        _apply(pending, seasons, game_label, players, clubs)
    elif back is not None:
        _apply(back, seasons, game_label, players, clubs, from_url=True)
    elif not st.session_state.get("_url_loaded"):
        _apply(dict(st.query_params), seasons, game_label, players, clubs, from_url=True)
    st.session_state["_url_loaded"] = True


def _back_forward():
    """The address after a browser Back/Forward, if one just happened. The
    viewport component sends it: Streamlit's st.query_params keeps the old
    address on that rerun."""
    v = st.session_state.get("viewport")
    if not isinstance(v, dict) or not v.get("pop") or v["pop"] == st.session_state.get("_last_pop"):
        return None
    st.session_state["_last_pop"] = v["pop"]
    return dict(parse_qsl(str(v.get("search", "")).lstrip("?")))


def write_url(season, view, game=None, player=None, opp=None, vs=None, games=None):
    """Keep the address in step with what is on screen."""
    state = {"season": str(season), "view": view}
    if view in ("Season", "Player") and games:
        state["games"] = games
    if view == "Match" and game:
        state["game"] = game
    if view == "Player" and player:
        state["player"] = player
        if vs:
            state["vs"] = vs
    if view == "Scout" and opp:
        state["opp"] = opp
    if dict(st.query_params) != state:
        st.query_params.from_dict(state)


def clicked(event):
    """The first clicked point of a chart selection event, or None."""
    try:
        points = event.selection["points"]
    except (AttributeError, KeyError, TypeError):
        return None
    return points[0] if points else None
