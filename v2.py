"""Coach View v2 (behind ?v2=1): five places around a coach's week.

Last game, Next opponent, Our season, Players and Game day, with the simulated
ground maps (heat maps, event spots, GPS running) and momentum charts on the
pages they belong to, and Wharf-ai always visible: beside the page on a desktop or landscape
tablet, docked to the bottom of the screen on a phone or portrait tablet. Pages
scroll under the top bar, so nothing is squeezed to fit one screen.

One of everything: one band (`band`), one tile row (`tiles`), one card header
(`finding`: a label, the takeaway as the headline, how to read it, and an "Ask
Wharf-ai" button), and one click rule (any game opens Last game for that game,
any player opens their profile in Players). The address holds the place and
picks: ?v2=1&season=2026&place=last-game&game=GF (player=, vs=, club=, games=).

Cards reused from views.py navigate with nav.go(view=...); `apply` translates
those moves to places, so their clicks follow the same rule.
"""

import html
from contextlib import contextmanager

import streamlit as st

import charts as CH
import data as D
import nav
import takeaways as T
import views as V
from theme import (COLORS, _avatar, _ordinal, _sparkline, card_title, club_colours, compare_table,
                   leaders_list, record_text, result_colour, tape)
import marks

PLACES = ["Last game", "Next opponent", "Our season", "Players", "Game day"]
# The first option of the club, player and compare pickers (a real option, so it shows).
EVERY_CLUB, SQUAD, NOBODY = "Every club", "The squad", "Compare with..."
SLUGS = {p: p.lower().replace(" ", "-") for p in PLACES}
FROM_SLUG = {v: k for k, v in SLUGS.items()}
OLD_VIEWS = {"Match": "Last game", "Scout": "Next opponent", "Season": "Our season",
             "Player": "Players"}
GROUND_H = 430         # the ground cards (simulated heat maps and events)
GROUND_NOTE = ("; the page also has SIMULATED ground maps (heat maps, event spots and GPS running: "
               "a demo, not real data): answer only from the real data, and if asked about "
               "positions, zones or running say the ground maps are a demo")
# The AFL's finals round names, shortened ("Qualifying & Elimination Finals" -> "Finals wk 1").
FINALS = [("Qualifying", "Finals wk 1"), ("Elimination", "Finals wk 1"), ("Semi", "SF"),
          ("Preliminary", "PF"), ("Grand", "GF")]


def short_round(api_round):
    name = str(api_round)
    return next((s for k, s in FINALS if k in name), name.replace("Round ", "Rd "))
CHART_H = 300          # a card's chart height; pages scroll, so this never has to shrink
TALL_H = 380
DOCK = False           # set by run(): Wharf-ai docked to the bottom (phones, portrait tablets)


def enabled():
    """?v2=1 turns v2 on for the session, ?v2=0 off."""
    q = st.query_params.get("v2")
    if q in ("1", "0"):
        st.session_state["v2"] = q == "1"
    return bool(st.session_state.get("v2"))


# ---- navigation ---------------------------------------------------------------
def go(**state):
    """Move somewhere: go(place="Last game", season=2026, game="GF")."""
    st.session_state["v2_pending"] = state
    st.rerun()


def _apply(state, ctx, from_url=False):
    season = state.get("season")
    try:
        season = int(season) if season is not None else None
    except (TypeError, ValueError):
        season = None
    if season in ctx["seasons"]:
        st.session_state["season"] = season
    season = st.session_state.get("season") or ctx["seasons"][-1]
    place = state.get("place")
    place = FROM_SLUG.get(place, place) or OLD_VIEWS.get(state.get("view"))
    if place in PLACES:
        st.session_state["v2_place"] = place
    if state.get("game"):
        label = ctx["game_label"](season, str(state["game"]))
        if label:
            st.session_state[f"v2_game_{season}"] = label
    players = ctx["players"](season)
    if "player" in state or from_url:
        pick = state.get("player")
        st.session_state["v2_player"] = pick if pick in players else SQUAD
        st.session_state["v2_vs"] = state.get("vs") if state.get("vs") in players else NOBODY
    club = state.get("club", state.get("opp"))
    if "club" in state or "opp" in state or from_url:
        st.session_state["v2_club"] = club if club in ctx["clubs"] else EVERY_CLUB
    if state.get("games") in D.GAME_SLICES:
        st.session_state["games_slice"] = state["games"]
    elif from_url:
        st.session_state["games_slice"] = D.GAME_SLICES[0]


def apply(ctx):
    """Before any control is drawn: a queued move (ours, or nav.go from a reused
    card), a browser Back/Forward, or on the first run the web address."""
    pending = st.session_state.pop("v2_pending", None) or st.session_state.pop("pending_nav", None)
    back = nav._back_forward()
    if pending:
        _apply(pending, ctx)
    elif back is not None:
        _apply(back, ctx, from_url=True)
    elif not st.session_state.get("_v2_url_loaded"):
        _apply(dict(st.query_params), ctx, from_url=True)
    st.session_state["_v2_url_loaded"] = True


def write_url(season, place, **picks):
    state = {"v2": "1", "season": str(season), "place": SLUGS[place]}
    state.update({k: str(v) for k, v in picks.items() if v})
    if dict(st.query_params) != state:
        st.query_params.from_dict(state)


def ask(question):
    """Send a question to Wharf-ai (it arrives on the next full run)."""
    st.session_state["pending_prompt"] = question
    st.session_state["wa_open"] = True        # docked: open the panel to show the answer
    st.rerun()


# ---- one of everything -----------------------------------------------------------
def band(title, sub="", lead=None, facts=(), form=None, avatars="", style="", cls=""):
    """The band at the top of every page. lead: (value HTML, label) shown big;
    facts: (value, label) pairs; form: [(result, tooltip)] chips; avatars: HTML."""
    parts = [avatars, f'<div class="ttl">{html.escape(title)}<small>{html.escape(sub)}</small></div>']
    if lead:
        parts.append(f'<div class="cv-stat hero"><b>{lead[0]}</b><span>{html.escape(lead[1])}</span></div>')
    parts += [f'<div class="cv-stat"><b>{v}</b><span>{html.escape(lbl)}</span></div>' for v, lbl in facts]
    if form:
        chips = "".join(f'<i title="{html.escape(t)}" style="background:{result_colour(r)}">{r}</i>'
                        for r, t in form)
        parts.append(f'<div class="cv-stat" title="Last 5 results"><div class="cv-form">{chips}</div></div>')
    st.markdown(f'<div class="cv-band v2 {cls}" style="{style}">{"".join(parts)}</div>',
                unsafe_allow_html=True)


def tiles(items):
    """One tile style everywhere. Each item: label, value (text), and optional
    rank (int), rank_bg, delta (text, colour), note, series/games/highlight."""
    cells = []
    for t in items:
        rk = ""
        if t.get("rank"):
            bg = f' style="background:{t["rank_bg"]}"' if t.get("rank_bg") else ""
            rk = f'<span class="rk"{bg}>{_ordinal(int(t["rank"]))}</span>'
        dlt = ""
        if t.get("delta"):
            text, colour = t["delta"]
            dlt = f'<span class="dlt" style="color:{colour}">{text}</span>'
        note = f'<div class="fr">{html.escape(t["note"])}</div>' if t.get("note") else ""
        spark = _sparkline(t["series"], t["games"], t.get("highlight")) if t.get("series") else ""
        cells.append(f'<div class="cv-tile"><div class="lbl">{html.escape(t["label"])}</div>'
                     f'<div class="val">{t["value"]}{rk}{dlt}</div>{note}{spark}</div>')
    st.markdown(f'<div class="cv-tiles v2">{"".join(cells)}</div>', unsafe_allow_html=True)


def _fmt(t, v):
    if v is None or v != v:
        return "-"
    return {"diff": f"{v:+.1f}", "acc": f"{v:.1f}%"}.get(t.get("kind"), f"{v:.1f}")


def from_stat_tiles(raw, versus):
    """season, match and player tiles (data.tiles and friends) -> tile items."""
    out = []
    for t in raw:
        item = {"label": t["label"], "value": _fmt(t, t["value"]), "series": t.get("series"),
                "games": t.get("games"), "highlight": t.get("highlight"), "rank": t.get("rank")}
        c = t.get("change")
        if c is not None and c == c:
            arrow = "▲" if c > 0 else ("▼" if c < 0 else "→")
            good = None if t.get("better") is None or c == 0 else (c > 0) == t["better"]
            colour = COLORS["muted"] if good is None else (COLORS["win"] if good else COLORS["loss"])
            item["delta"] = (f"{arrow} {c:+.1f}{t['unit']}", colour)
            item["note"] = f"{versus}: {_fmt(t, t['base'])}"
        out.append(item)
    return out


@contextmanager
def finding(name, label, headline="", how="", question=None):
    """The one card: a label, the takeaway as its headline, how to read it, and an
    "Ask Wharf-ai" button that sends `question` to the panel."""
    with V.card(name):
        if question:
            t, b = st.columns([4.2, 1], vertical_alignment="top")
            with b:
                if st.button("Ask", key=f"ask_{name}", icon=":material/forum:",
                             type="tertiary", help=f"Ask Wharf-ai: {question}"):
                    ask(question)
        else:
            t = st.container()
        with t:
            card_title(label, how, takeaway=headline)
        yield


def grid(rows):
    """rows: [(column ratios, [card functions])]. Beside Wharf-ai the ratios
    hold; docked (narrow screens) every card takes the full width."""
    for ratios, parts in rows:
        if DOCK or len(parts) == 1:
            for part in parts:
                part()
            continue
        for col, part in zip(st.columns(ratios), parts):
            with col:
                part()


def _open_game_from(event, labels, season):
    point = nav.clicked(event)
    if point and point.get("x") in labels:
        go(place="Last game", season=season, game=str(point["x"]).split(" ")[0])


def _table_pick(df, key, on_pick, height=None, config=None):
    """A table whose rows open something: on_pick(row index)."""
    n = st.session_state.get(f"{key}_n", 0)
    ev = st.dataframe(df, hide_index=True, width="stretch", row_height=28, column_config=config,
                      height=height or "auto", on_select="rerun", selection_mode="single-row",
                      key=f"{key}_{n}")
    rows = (ev.selection.get("rows") if ev and hasattr(ev, "selection") else None) or []
    if rows:
        st.session_state[f"{key}_n"] = n + 1          # a fresh table next time, no stale pick
        on_pick(rows[0])


# ---- places --------------------------------------------------------------------
def last_game(ctx, season, tdf, pdf, pos):
    game = tdf.iloc[pos]
    opp = game["opponent"]
    club = club_colours(opp)
    short = D.abbr(opp)
    margin = abs(int(game["margin"]))
    res = {"W": f"Won by {margin}", "L": f"Lost by {margin}"}.get(game["result"], "Drew")
    fq, oq = game["freo_qtrs"].split()[-1], game["opp_qtrs"].split()[-1]
    score = f'{game["freo_score"]} <em>&nbsp;v&nbsp;</em> {game["opp_score"]}'
    pill = f'<i class="cv-res" style="background:{result_colour(game["result"])}">{res}</i>'
    band(f"{game['round']} v {opp}", f"{game['venue']} · {game['game_dt']:%a %d %b %Y} · {game['type']}",
         lead=(score, f"Freo {fq} · {short} {oq}"), facts=[(pill, "Result")],
         style=(f"background:linear-gradient(100deg, var(--brand) 0%, var(--brand-2) 45%, "
                f"{club['band']} 100%); border-right:6px solid {club['accent']}; "
                f"--mark:{marks.uri(opp)}"), cls="match")
    tiles(from_stat_tiles(D.match_tiles(ctx["team"], season, pos), "Season avg"))

    def momentum_card():
        ev = D.game_events(game)
        if ev is None:
            with finding("v2_flow", "Game flow", "", "margin at each break"):
                flow, avg = D.game_flow(tdf, pos)
                _plot(CH.game_flow_lines(flow, avg, CHART_H))
            return
        events, quarters = ev
        runs = D.scoring_runs(events)
        run = runs.iloc[0] if len(runs) and runs.iloc[0]["goals"] >= D.RUN_GOALS else None
        with finding("v2_momentum", "Momentum",
                     T.momentum(events, run, game["result"], int(game["margin"]), short),
                     "the margin after every score; bars: who had been scoring lately",
                     question="When did this game turn, and what changed?"):
            _plot(CH.momentum_chart(events, quarters, D.momentum(events, quarters), run, TALL_H,
                                    opp=short, opp_color=club["chart"]))

    def tape_card():
        rows = D.tale_of_the_tape(tdf, pos)
        with finding("v2_tape", "Tale of the tape", T.tape(rows), "tick: Freo's season average share",
                     question="Which counts decided this game?"):
            tape(rows, opp_color=club["chart"], names=("Freo", short))

    def ground_card():
        V.match_ground_card(ctx["player_df"], season, game, GROUND_H)

    def leaders_card():
        leaders, goals = D.match_leaders(pdf, game)
        theirs = D.opp_match_leaders(game)
        with finding("v2_leaders", "Game leaders", T.match_leaders(goals, theirs[1], short) if theirs
                     else T.match_leaders(goals), "Freo's leaders open the player",
                     question="Who were our best players in this game?"):
            names = {f"{l['role']}: {l['player'].split()[-1]} {l['value']}": l["player"] for l in leaders}
            n = st.session_state.get("v2_lead_n", 0)
            pick = st.pills("Freo leaders", list(names), key=f"v2_lead_{season}_{game['round']}_{n}",
                            label_visibility="collapsed")
            if pick:
                st.session_state["v2_lead_n"] = n + 1
                go(place="Players", season=season, player=names[pick], vs=None)
            if theirs is not None:
                line = " · ".join(f"{l['role']}: {l['player'].split()[-1]} {l['value']}"
                                  for l in theirs[0])
                st.markdown(f'<div class="v2-line"><b>{html.escape(short)}</b> · {html.escape(line)}</div>',
                            unsafe_allow_html=True)

    def players_card():
        V._match_players(pdf, game, season, pos, TALL_H)

    grid([([1.55, 1], [momentum_card, ground_card]), ([1.1, 1], [tape_card, leaders_card]),
          ([1], [players_card])])
    return (f"{game['round']} v {opp} at {game['venue']}, "
            + ("drew" if game["result"] == "D" else
               f"{'won' if game['result'] == 'W' else 'lost'} by {margin}") + GROUND_NOTE)


def next_opponent(ctx, season, club):
    lg = ctx["league"]
    if lg is None:
        st.info("Next opponent needs the league file (league_scraper.py).")
        return None
    if club is None:
        return club_index(ctx)
    colours = club_colours(club)
    lad = D.ladder(lg, season)
    games = lg[(lg["season"] == season) & (lg["team"] == club)]
    row = lad.loc[club] if club in lad.index else None
    form = [(r.result, f"{r.api_round} v {r.opponent}: {r.score_for} to {r.score_against}")
            for r in games.tail(5).itertuples()]
    facts = []
    if row is not None:
        rec = f'{int(row["wins"])}-{int(row["losses"])}' + (f'-{int(row["draws"])}' if row["draws"] else "")
        facts = [(rec, "Home and away"), (f'{row["pct"]:.1f}', "Percentage")]
    band(club, f"{season} · scout report", lead=(_ordinal(int(row["position"])), "Ladder") if row is not None else None,
         facts=facts, form=form,
         style=f"background:{colours['band']}; border-left:6px solid {colours['accent']}; --mark:{marks.uri(club)}",
         cls="club")
    tiles([{"label": t["label"], "value": t["value"], "rank": t["rank"], "rank_bg": colours["band"],
            "note": f"Freo {t['freo']}"} for t in D.scout_tiles(lg, club, season)])
    short = D.abbr(club)
    tint, grey = colours["chart"], colours["vs"]
    last5 = games.tail(5)

    def last5_card():
        shown, runs = [], []
        for g in last5.itertuples():
            ev = D.club_game_events(g._asdict())
            rnd = short_round(g.api_round)
            label = f"{rnd} v {D.abbr(g.opponent)} · {g.result} {int(g.margin):+d}"
            if ev is None:
                continue
            events, quarters = ev
            r = D.scoring_runs(events)
            runs.append((label.split(" · ")[0], r.iloc[0] if len(r) else None))
            shown.append((label, events, quarters, D.momentum(events, quarters)))
        with finding("v2_last5", "Their last 5 games", T.club_last5(last5, runs, short),
                     f"each game from {short}'s side: the margin after every score, then who had "
                     "been scoring lately", question=f"How have {club} been winning and losing "
                     "their recent games: fast starts or strong finishes?"):
            if not shown:
                st.caption("Scores in order for these games aren't in the data yet "
                           "(league_events_scraper.py).")
                return
            fig = CH.momentum_multiples(shown, 300 if not DOCK else 230 * len(shown), short, tint, grey,
                                        cols=None if not DOCK else 1)
            _plot(fig)

    def heat_card():
        import sim
        rows, role = sim.team_rows(last5, club)
        V._ground_card("v2_opp_ground", rows, role, GROUND_H, f"{short}, last 5 games", attack=short)

    def sim_card():
        sim_card_body(club, short, tint)

    def style_card():
        avg, ranks = D.team_ranks(lg, season)
        with finding("v2_style", "Style vs league", T.style(ranks, club), "rank of 18 on each stat",
                     question=f"Where are {club} weakest compared with the league?"):
            _plot(CH.rank_dumbbell(avg, ranks, club, D.SCOUT_STATS, CHART_H, team_color=tint,
                                   focus=T.style_marks(ranks, club)))

    def win_card():
        wc = D.scout_win_conditions(lg, club, season)
        with finding("v2_theywin", "How they win", T.where_we_win(wc),
                     "win rate when each side won the count",
                     question=f"What wins {club} games?"):
            _plot(CH.win_dumbbell(wc, CHART_H, names=(f"{short} won it", "Their opponent won it"),
                                  colors=(tint, grey), focus=T.swing_stat(wc)))

    def quarters_card():
        qp = D.scout_quarters(lg, club, season)
        with finding("v2_theirq", "Their quarters", T.quarters(qp), "average points",
                     question=f"Which quarters do {club} win?"):
            _plot(CH.quarter_bars(qp, CHART_H, names=(club, "Opponents"), colors=(tint, grey),
                                  focus=T.best_worst_quarter(qp)))

    def form_card():
        last = games.tail(14)
        with finding("v2_theirform", "Their form", T.scout_form(last),
                     f"last {len(last)} games, green win, red loss"):
            _plot(CH.form_bars(last, CHART_H))

    def h2h_card():
        rows = D.head_to_head(ctx["team"], club)
        with finding("v2_h2h", "Against Fremantle", T.h2h(rows), "every game, all seasons · click a game",
                     question=f"How have we gone against {club}, and what decided those games?"):
            if not len(rows):
                st.caption("No games against Fremantle in the data.")
                return
            show = rows.assign(
                Game=rows["season"].astype(str) + " " + rows["round"],
                Result=[f"{r} {m:+d}" if r != "D" else "D" for r, m in zip(rows["result"], rows["margin"])],
                Score=rows["freo_score"].astype(str) + "-" + rows["opp_score"].astype(str))
            cols = ["Game", "venue", "Result", "Score"]
            if "freo_inside_50s" in rows:
                show["I50 diff"] = rows["freo_inside_50s"] - rows["opp_inside_50s"]
                show["CP diff"] = rows["freo_contested_poss"] - rows["opp_contested_poss"]
                cols += ["I50 diff", "CP diff"]
            show = show[cols].rename(columns={"venue": "Venue"})
            _table_pick(show, f"v2h2h_{club}", lambda i: go(
                place="Last game", season=int(rows["season"].iloc[i]), game=rows["round"].iloc[i]))

    grid([([1], [sim_card]), ([1], [last5_card]), ([1.1, 1], [heat_card, style_card]),
          ([1.1, 1], [win_card, quarters_card]), ([1, 1.1], [form_card, h2h_card])])
    return (f"the opponent scout report for {club}, {season} season" + GROUND_NOTE
            + f"; it also shows a model FORECAST of Freo v {club} (simulated games from a model, not "
            "data): answer from the real data, and say any forecast on the page comes from the model")


@st.cache_resource(show_spinner=False)
def _match_model():
    import model as M
    return M.app_model()


@st.cache_data(show_spinner=False)
def _forecast(club, venue):
    import model as M
    m, lg, X = _match_model()
    f = M.forecast(m, lg, X, "Fremantle", club, venue)
    return {k: v for k, v in f.items() if k != "points"}


VENUES = {"At home": 1, "Away": -1, "Neutral": 0}


def sim_card_body(club, short, tint):
    """Freo v the club, simulated 10,000 times by the match model (model.py): win
    chance, likely margins, each side's chance of a 3+ goal run, and one example
    game as a momentum chart. Plainly a forecast, with how the model tested."""
    import model as M
    ev = M.load_eval()
    venue = st.session_state.get("v2_sim_venue") or "At home"
    f = _forecast(club, VENUES[venue])
    win, lose = f["win"], 1 - f["win"] - f["draw"]
    where = {"At home": "at home", "Away": "away", "Neutral": "at a neutral ground"}[venue]
    head = (f"Freo win {win:.0%} of 10,000 simulated games {where}; {short} {lose:.0%}. "
            f"Typical margin {'level' if round(f['p50']) == 0 else format(f['p50'], '+.0f')}, "
            f"8 in 10 between {f['p10']:+.0f} and {f['p90']:+.0f}")
    with finding("v2_sim", f"Simulate Freo v {short}", head,
                 "a forecast from both clubs' recent form (whole-game stats): MODEL, not a result",
                 question=f"How would we go against {club}, and what would decide it?"):
        st.segmented_control("Venue", list(VENUES), default="At home", key="v2_sim_venue",
                             label_visibility="collapsed")
        g = f["lam"] * f["acc"]
        b = f["lam"] - g
        tiles([
            {"label": "Freo win chance", "value": f"{win:.0%}", "note": f"{short} {lose:.0%}, draw {f['draw']:.0%}"},
            {"label": "Likely margin", "value": "Level" if round(f["p50"]) == 0 else f"{f['p50']:+.0f}",
             "note": f"8 in 10: {f['p10']:+.0f} to {f['p90']:+.0f}"},
            {"label": "Expected score", "value": f"{g[0]:.0f}.{b[0]:.0f} v {g[1]:.0f}.{b[1]:.0f}",
             "note": f"{f['lam'][0] * (1 + 5 * f['acc'][0]):.0f} v {f['lam'][1] * (1 + 5 * f['acc'][1]):.0f} points"},
            {"label": "A 3+ goal run", "value": f"{f['run_chance'][0]:.0%}",
             "note": f"Freo's chance; {short} {f['run_chance'][1]:.0%}"},
        ])
        c1, c2 = (st.container(), st.container()) if DOCK else st.columns([1, 1.5])
        with c1:
            _plot(CH.margin_histogram(f["margin"], CHART_H, us="Freo", them=short, them_color=tint))
        with c2:
            n = st.session_state.get("v2_sim_seed", 0)
            m, *_ = _match_model()
            e = M.one_game(f["lam"], f["acc"], m.k, f["shares"], f["qlen"], seed=10_000 + n, kq=m.kq,
                           stick=m.stick)
            if e is not None:
                events, quarters = e
                runs = D.scoring_runs(events)
                run = runs.iloc[0] if len(runs) and runs.iloc[0]["goals"] >= D.RUN_GOALS else None
                mg = int(events["margin"].iloc[-1])
                res = "W" if mg > 0 else "L" if mg < 0 else "D"
                st.markdown(f'<div class="card-take">One simulated game: '
                            f'{html.escape(T.momentum(events, run, res, mg, short))}</div>',
                            unsafe_allow_html=True)
                _plot(CH.momentum_chart(events, quarters, D.momentum(events, quarters), run, CHART_H,
                                        opp=short, opp_color=tint, tag="SIMULATED"))
            if st.button("Simulate another game", key="v2_sim_again", icon=":material/refresh:",
                         type="tertiary"):
                st.session_state["v2_sim_seed"] = n + 1
                st.rerun()
        if ev:
            st.caption(f"How good is it? Tested on all {ev['games']} games of {ev['test']}, each predicted "
                       f"from form before it was played: it tipped {ev['model']['tips']:.0%} "
                       f"(recent form alone {ev['form']['tips']:.0%}, home ground alone "
                       f"{ev['home']['tips']:.0%}), with an average margin error of "
                       f"{ev['model']['mae']:.0f} points. It knows nothing of injuries, selection, "
                       "weather or tactics.")


def club_index(ctx):
    """Every club Freo have played, all seasons, toughest first; a row opens the club."""
    grid_rows = D.opponent_grid(ctx["team"])
    band("Every club", "every Freo game, all seasons · pick a club for its scout report",
         lead=(str(len(grid_rows)), "Clubs"))
    seasons = ctx["seasons"]

    def card():
        with finding("v2_clubs", "Every club", T.clubs(grid_rows), "toughest first · click a club",
                     question="Which opponents have we struggled against, and why?"):
            import pandas as pd
            table = pd.DataFrame([{
                "Club": r["opponent"],
                "Record": record_text(r["wins"], r["losses"], r["draws"]),
                "Avg margin": round(r["avg_margin"], 1),
                **{str(s): "  ".join(f"{g['round']} {g['margin']:+d}" for g in r["games"].get(s, []))
                   for s in seasons}} for r in grid_rows])
            _table_pick(table, "v2clubs", lambda i: go(place="Next opponent", club=table["Club"].iloc[i]),
                        height=38 + 28 * len(table),
                        config={"Avg margin": st.column_config.NumberColumn(format="%+.1f")})

    grid([([1], [card])])
    return "every Freo game against every club, all seasons"


def our_season(ctx, season, baseline, tdf, pdf, games_slice):
    rec = D.record(tdf)
    note = (f"{len(tdf)} games to {tdf['round'].iloc[-1]}, {tdf['game_dt'].iloc[-1]:%d %b}"
            if len(tdf) else "No games")
    if baseline is not None:
        note += f" · compared with {baseline}"
    if games_slice != D.GAME_SLICES[0]:
        note = f"{games_slice} only · " + note
    form = [(r.result, f"{r.round} vs {r.opponent}: {r.freo_score} to {r.opp_score}")
            for r in tdf.tail(5).itertuples()]
    band(f"Fremantle {season}", note,
         lead=(record_text(rec["wins"], rec["losses"], rec.get("draws", 0)), "Record"),
         facts=[(f'{rec["win_pct"]:.0f}%', "Win rate"), (f'{rec["margin"]:+.1f}', "Avg margin"),
                (f'{rec["score_for"]:.1f}', "Avg for"), (f'{rec["score_against"]:.1f}', "Avg against")],
         form=form)
    if not len(tdf):
        st.info(f"No {games_slice.lower()} in {season}. Pick another slice of games.")
        return None
    tiles(from_stat_tiles(D.tiles(ctx["team_view"], season, baseline), str(baseline)))

    def strip_card():
        rows, z, hover, labels = D.game_strip(tdf, runs=True)
        with finding("v2_strip", "Game by game", T.strip(tdf),
                     "each count shaded by who won it: purple Freo, cyan the opposition · click a game",
                     question="What do our losses have in common?"):
            ev = _plot(CH.game_strip(rows, z, hover, labels, tdf["result"].tolist(), CHART_H,
                                     focus=T.top_driver(D.margin_drivers(tdf))), key=f"v2strip_{season}")
            _open_game_from(ev, labels, season)

    def wins_card():
        ww = D.what_wins(tdf)
        with finding("v2_wins", "What wins us games", T.where_we_win(ww),
                     "win rate when each side won the count; r: how the count tracks the margin "
                     "(association, not cause)",
                     question="Which counts matter most to whether we win?"):
            _plot(CH.win_dumbbell(ww, CHART_H, focus=T.swing_stat(ww), show_r=True))

    def quarters_card():
        qp = D.quarter_pattern(tdf)
        with finding("v2_quarters", "Quarters", T.quarters(qp), "average points a quarter, then "
                     "inside each quarter: F first 10 minutes, M middle, L last 10",
                     question="Which quarter do we fade in, and against whom?"):
            _plot(CH.quarter_bars(qp, CHART_H - 40, focus=T.best_worst_quarter(qp)))
            if D.load_score_events() is not None:
                w, _ = D.window_scoring(tdf)
                st.markdown(f'<div class="card-take">{html.escape(T.windows(w))}</div>',
                            unsafe_allow_html=True)
                _plot(CH.window_bars(w, CHART_H - 40, focus=T.window_focus(w)))

    def momentum_card():
        if D.load_score_events() is None:
            return
        test = D.momentum_test(ctx["team"][ctx["team"]["season"].isin(ctx["seasons"])])
        runs = D.run_table(tdf)
        head = T.carry(test, f"{ctx['seasons'][0]}-{ctx['seasons'][-1]}")
        with finding("v2_mom", "Momentum", head,
                     "does the side that kicked the last goal kick the next? Then every run of "
                     f"{D.RUN_GOALS}+ goals · click a run for the game",
                     question="How quickly do we answer the opposition's runs?"):
            tests = {str(s): D.momentum_test(D.team_season(ctx["team"], s)) for s in ctx["seasons"]}
            tests["All"] = test
            _plot(CH.carry_dots({k: v for k, v in tests.items() if v}, 200))
            side = st.segmented_control("Runs", ["Against Freo", "By Freo"], default="Against Freo",
                                        key="v2_runs_side") or "Against Freo"
            mine = runs[runs["team"] == ("Opp" if side == "Against Freo" else "Freo")] if len(runs) else runs
            st.markdown(f'<div class="card-take">{html.escape(T.run_list(mine, side == "Against Freo"))}</div>',
                        unsafe_allow_html=True)
            if len(mine):
                import pandas as pd
                show = pd.DataFrame({
                    "Game": mine["round"] + " v " + mine["opponent"].map(D.abbr),
                    "Result": [f"{r} {m:+d}" if r != "D" else "D" for r, m in
                               zip(mine["result"], mine["margin_final"])],
                    "Run": mine["goals"].astype(str) + "." + mine["behinds"].astype(str),
                    "From": mine["starts"], "Minutes": mine["minutes"],
                    "Margin": [f"{a:+d} to {b:+d}" for a, b in zip(mine["margin_before"], mine["margin_after"])],
                    "Reply (min)": [f"{v:.1f}" if v == v and v is not None else "" for v in mine["answered_in"]]})
                _table_pick(show, f"v2runs_{season}_{side}",
                            lambda i: go(place="Last game", season=season, game=mine["round"].iloc[i]),
                            height=min(36 + 28 * len(show), 320))

    def ground_card():
        import sim
        V._ground_card("v2_season_ground", pdf, sim.roles(ctx["player_df"]), GROUND_H + 160,
                       f"the team in {season}")

    grid([([1], [strip_card]), ([1, 1], [wins_card, quarters_card]), ([1.6, 1], [momentum_card, ground_card])])
    focus = None if games_slice == D.GAME_SLICES[0] else f"the {season} season, {games_slice.lower()} only"
    return (focus or f"the {season} season") + GROUND_NOTE


def players(ctx, season, baseline, pdf, player, vs, games_slice):
    if player is None:
        return squad(ctx, season, baseline, pdf, games_slice)
    if not (pdf["player"] == player).any():
        st.info(f"{player} didn't play in {games_slice.lower()} in {season}.")
        return None
    if vs:
        return compare(ctx, season, pdf, player, vs)
    details = D.player_details(ctx["player_df"], player, season)
    me = pdf[pdf["player"] == player].sort_values("game_dt")
    jumper = int(me["jumper"].iloc[-1]) if len(me) else None
    bits = [f"#{jumper}" if jumper else None, details.get("position"),
            f"{details['age']} yrs" if details.get("age") else None,
            f"{details['height_cm']} cm" if details.get("height_cm") else None]
    top = details.get("top")
    band(player, " · ".join(b for b in bits if b) or f"{season} season",
         lead=(_ordinal(top["rank"]), f"{top['stat']} in squad") if top else None,
         facts=[(str(len(me)), "Games"), (str(int(me["goals"].sum())), "Goals")],
         avatars=_avatar(player, ctx["photo"](details.get("player_id"), season)), cls="player")
    tiles(from_stat_tiles(D.player_tiles(ctx["player_view"], player, season, baseline), str(baseline)))
    trend_stats = {k: v for k, v in V.PLAYER_TREND_STATS.items() if v in pdf.columns}
    first = player.split()[0]

    def trend_card():
        label = st.session_state.get("v2_trend_stat") or "Disposals"
        col = trend_stats.get(label, "disposals")
        with finding("v2_ptrend", "Game by game", T.player_trend(me, col, label),
                     "dots green win, red loss", question=f"Is {first} in form over the last five games?"):
            st.selectbox("Stat", list(trend_stats), key="v2_trend_stat", label_visibility="collapsed")
            _plot(CH.player_trend(me, col, label, CHART_H))

    def ranks_card():
        pr = D.player_squad_ranks(pdf, player)
        with finding("v2_pranks", "Squad rank", T.player_ranks(pr),
                     f"per game, of players with {D.MIN_GAMES}+ games",
                     question=f"Where does {first} rank in the squad?"):
            if len(pr):
                _plot(CH.squad_rank_bars(pr, CHART_H + 40, focus=T.rank_focus(pr)))
            else:
                st.caption(f"Needs {D.MIN_GAMES} games for a squad rank.")

    def range_card():
        V._player_log(pdf, player, TALL_H)

    def ground_card():
        V.player_ground_card(ctx["player_df"], season, player, GROUND_H)

    grid([([1.6, 1], [trend_card, ranks_card]), ([1.6, 1], [range_card, ground_card])])
    focus = f"the player profile for {player}, {season} season"
    return focus + (f", {games_slice.lower()} only" if games_slice != D.GAME_SLICES[0] else "") + GROUND_NOTE


def compare(ctx, season, pdf, a, b):
    names = (a, b)
    logs = [pdf[pdf["player"] == n].sort_values("game_dt") for n in names]
    cmp = D.compare_players(pdf, a, b)
    together = D.games_together(pdf, a, b)
    photos = [ctx["photo"](D.player_details(ctx["player_df"], n, season).get("player_id"), season)
              for n in names]
    band(f"{a.split()[-1]} v {b.split()[-1]}", f"{season} · {together['games']} games together",
         lead=(record_text(together["wins"], together["losses"], together.get("draws", 0)),
               "Record together"),
         facts=[(f"{together['games_a']} / {together['games_b']}", "Games each")],
         avatars=_avatar(a, photos[0], ring=CH.PAIR[0]) + _avatar(b, photos[1], ring=CH.PAIR[1]),
         cls="player cmp")
    items = []
    for label, _ in D.PLAYER_TILES:
        r = cmp[cmp["stat"] == label]
        if not len(r):
            continue
        r = r.iloc[0]
        rank = lambda k: _ordinal(int(r[k])) if r[k] == r[k] and r[k] else "-"   # noqa: E731
        items.append({"label": label,
                      "value": (f'<span style="color:{CH.PAIR[0]}">{r["avg_a"]:.1f}</span>'
                                f'<small> v </small><span style="color:{CH.PAIR[1]}">{r["avg_b"]:.1f}</span>'),
                      "note": f"{a.split()[-1]} {rank('rank_a')} · {b.split()[-1]} {rank('rank_b')} in squad"})
    tiles(items)
    trend_stats = {k: v for k, v in V.PLAYER_TREND_STATS.items() if v in pdf.columns}

    def trend_card():
        label = st.session_state.get("v2_trend_stat") or "Disposals"
        col = trend_stats.get(label, "disposals")
        with finding("v2_ctrend", "Game by game", T.compare_last(logs, names, col, label),
                     "dashed: season averages",
                     question=f"Who is in better form, {a.split()[-1]} or {b.split()[-1]}?"):
            st.selectbox("Stat", list(trend_stats), key="v2_trend_stat", label_visibility="collapsed")
            season_games = pdf.drop_duplicates(["round"])[["round", "opponent", "game_dt"]]
            _plot(CH.compare_trend(season_games, logs, names, col, label, CHART_H))

    def ranks_card():
        with finding("v2_cranks", "Squad rank", T.compare_ahead(cmp, names),
                     f"per game, of players with {D.MIN_GAMES}+ games"):
            if cmp[["rank_a", "rank_b"]].notna().all(axis=1).any():
                _plot(CH.compare_ranks(cmp, names, CHART_H + 40))
            else:
                st.caption(f"Both need {D.MIN_GAMES} games for a squad rank.")

    def table_card():
        with finding("v2_ctable", "Stat by stat", T.compare_gap(cmp, names), "per game, season and last 5",
                     question=f"Where is {a.split()[-1]} ahead of {b.split()[-1]}, and where is he behind?"):
            compare_table(cmp, names)

    grid([([1.6, 1], [trend_card, ranks_card]), ([1], [table_card])])
    return f"a comparison of {a} and {b}, {season} season"


def squad(ctx, season, baseline, pdf, games_slice):
    rec = D.record(D.team_season(ctx["team_view"], season))
    band("The squad", f"{season} · {pdf['player'].nunique()} players · pick a player for their profile",
         lead=(str(pdf["player"].nunique()), "Players used"),
         facts=[(record_text(rec["wins"], rec["losses"], rec.get("draws", 0)), "Record")])
    form_stats = V.FORM_STATS_EXT if "pressure_acts" in pdf.columns else V.FORM_STATS
    stats = {k: v for k, v in V.SQUAD_STATS.items() if v in pdf.columns}
    labels = list(stats)

    def form_card():
        stat = st.session_state.get("v2_form_stat") or "Disposals"
        vals, avgs, _ = D.form_matrix(pdf, form_stats.get(stat, "disposals"), n_players=12)
        with finding("v2_form", "Who's up, who's down", T.form(vals, avgs) if len(vals) else "",
                     "last 3 games against own season average · click a player",
                     question="Which players are in the best form right now?"):
            st.selectbox("Form stat", list(form_stats), key="v2_form_stat", label_visibility="collapsed")
            last3, pct = T.form_change(vals, avgs) if len(vals) else ([], [])
            if len(pct):
                ev = _plot(CH.form_dumbbell(last3, avgs, pct, stat, CHART_H + 40,
                                            focus=T.hot_player(vals, avgs)), key=f"v2form_{season}_{stat}")
                point = nav.clicked(ev)
                if point and point.get("y"):
                    go(place="Players", season=season, player=str(point["y"]), vs=None)

    def leaders_card():
        leaders = D.role_leaders(pdf)
        with finding("v2_roles", "Role leaders", T.leaders(leaders), "most games led"):
            gk = D.top_goalkickers(pdf, n=1)
            if len(gk):
                leaders.append({"role": "Top goalkicker", "player": gk.index[0],
                                "value": f"{int(gk['goals'].iloc[0])}",
                                "sub": f"goals in {int(gk['games'].iloc[0])} games"})
            names = {f"{l['role']}: {l['player']}": l["player"] for l in leaders}
            n = st.session_state.get("v2_roles_n", 0)
            pick = st.pills("Leaders", list(names), key=f"v2_roles_{season}_{n}",
                            label_visibility="collapsed")
            if pick:
                st.session_state["v2_roles_n"] = n + 1
                go(place="Players", season=season, player=names[pick], vs=None)

    def map_card():
        x = st.session_state.get("v2_map_x") or "Contested poss"
        y = st.session_state.get("v2_map_y") or ("Metres gained" if "Metres gained" in stats else "Uncontested poss")
        size_col = "time_on_ground_pct" if "time_on_ground_pct" in pdf.columns else "pct_played"
        pa = D.player_averages(pdf, [stats[x], stats[y], size_col])
        with finding("v2_map", "Player map", T.squad_map(pa, stats[x], stats[y], x, y) if len(pa) else "",
                     "per game, 5+ games, dot size: time on ground · click a player"):
            c1, c2 = st.columns(2)
            c1.selectbox("Across", labels, index=labels.index(x), key="v2_map_x",
                         format_func=lambda v: f"Across: {v}", label_visibility="collapsed")
            c2.selectbox("Up", labels, index=labels.index(y), key="v2_map_y",
                         format_func=lambda v: f"Up: {v}", label_visibility="collapsed")
            if len(pa):
                ev = _plot(CH.player_map(pa, stats[x], stats[y], x, y, size_col, TALL_H),
                           key=f"v2map_{season}_{x}_{y}")
                point = nav.clicked(ev)
                if point is not None and point.get("point_index") is not None:
                    go(place="Players", season=season, player=pa.index[point["point_index"]], vs=None)

    def yoy_card():
        if baseline is None:
            return
        base_stats = [k for k in labels if stats[k] in D.players_season(ctx["player_df"], baseline)]
        stat = st.session_state.get("v2_yoy_stat") or base_stats[0]
        yoy = D.year_on_year(ctx["player_df"], baseline, season, stats[stat])
        with finding("v2_yoy", "Year on year", T.year_on_year(yoy) if len(yoy) else "",
                     f"{baseline} to {season}, top 15 with 8+ games in both · click a player",
                     question=f"Who are our most improved players since {baseline}?"):
            st.selectbox("Stat", base_stats, key="v2_yoy_stat", label_visibility="collapsed")
            if len(yoy):
                ev = _plot(CH.slope_chart(yoy, baseline, season, stat, TALL_H), key=f"v2yoy_{season}_{stat}")
                point = nav.clicked(ev)
                if point is not None and point.get("curve_number") is not None:
                    go(place="Players", season=season, player=yoy.index[point["curve_number"]], vs=None)

    grid([([1.6, 1], [form_card, leaders_card]), ([1.2, 1], [map_card, yoy_card])])
    return f"the whole squad (player map and year on year), {season} season"


def game_day(ctx, season, sz):
    band("Game day", "how Freo have gone from a margin at a break, every season",
         lead=(str(len(ctx["team"])), "Games to compare"))
    V.render_quarter_time(ctx["team"], ctx["seasons"], sz)
    return "the quarter-time check (how Freo have gone from a margin at a break)"


def _plot(fig, key=None):
    return V._plot(fig, key=key)


# ---- the shell -----------------------------------------------------------------
def run(ctx):
    """Draw v2. ctx: the app's data, helpers and the Wharf-ai panel."""
    global DOCK
    win_w, win_h = ctx["win"]
    DOCK = win_w < 1000 or win_h < 600
    phone = win_w < 700
    compact = win_w < 1000            # two-line top bar: one line can't hold the six places
    V.set_layout("phone" if phone else "split")      # reused cards: content heights, touch charts
    inject_css(DOCK, win_h)
    seasons = ctx["seasons"]
    apply(ctx)

    with st.container(key="topbar"):
        if compact:   # two lines: the seasons and icons, then the place across the width
            h2, _sp, h5, h6 = st.columns([1.1, 1.3, 0.3, 0.3], vertical_alignment="center")
            h3 = st.container()
        else:
            sw = 0.55 * len(seasons)
            hb, h2, h3, _g, h4, h5, h6 = st.columns([1.7, sw, 6.2, max(0.2, 2.4 - sw), 0.3, 0.3, 0.3],
                                                    vertical_alignment="center")
            with hb:
                ctx["brand_title"]()
            with h4:
                ctx["usage_button"]()
    with h2:
        season = st.segmented_control("Season", seasons, default=seasons[-1], key="season",
                                      label_visibility="collapsed") or seasons[-1]
    with h3:
        if st.session_state.get("v2_place") not in PLACES:
            st.session_state["v2_place"] = PLACES[0]
        if phone:
            place = st.selectbox("Place", PLACES, key="v2_place", label_visibility="collapsed")
        else:         # tablets put the links on their own line (compact), desktops in the bar
            place = st.segmented_control("Place", PLACES, key="v2_place",
                                         label_visibility="collapsed") or PLACES[0]
    with h5:
        if st.button("?", key="tour_btn", help="Take the app tour"):
            ctx["tour_replay"]()
    with h6:
        ctx["signout_button"]()

    baseline = D.baseline_season(season, seasons)
    if DOCK:
        main = st.container()
    else:
        main, side = st.columns([3.2, 1])
    picks = {}
    with main:
        focus = _place(ctx, place, season, baseline, picks)
    write_url(season, place, **picks)
    if DOCK:
        dock(ctx, season, baseline, focus)
    else:
        with side, st.container(border=True, height=win_h - 60, key="card_wharfai"):
            ctx["chat_panel"](season, baseline, focus)


def _place(ctx, place, season, baseline, picks):
    """The picker row and the page for one place; fills picks for the address."""
    team = ctx["team"]
    tdf = D.team_season(team, season)
    if place == "Last game":
        choices = D.game_choices(tdf)
        if not choices:
            st.info(f"No games in {season}.")
            return None
        labels = [c[0] for c in choices]
        key = f"v2_game_{season}"
        if st.session_state.get(key) not in labels:
            st.session_state[key] = labels[0]
        c, _ = st.columns([1.2, 3])
        label = c.selectbox("Game", labels, key=key, label_visibility="collapsed")
        pos = dict(choices)[label]
        picks["game"] = tdf["round"].iloc[pos]
        return last_game(ctx, season, tdf, D.players_season(ctx["player_df"], season), pos)
    if place == "Next opponent":
        clubs = ctx["clubs"]
        if st.session_state.get("v2_club") not in clubs:
            st.session_state["v2_club"] = EVERY_CLUB
        c, b, _ = st.columns([1.2, 0.8, 2.2], vertical_alignment="center")
        club = c.selectbox("Club", [EVERY_CLUB] + clubs, key="v2_club", label_visibility="collapsed")
        club = None if club == EVERY_CLUB else club
        if club is not None and b.button("Every club", key="v2_all_clubs", icon=":material/arrow_back:",
                                         type="tertiary"):
            go(club=None)
        picks["club"] = club
        return next_opponent(ctx, season, club)
    if place == "Game day":
        return game_day(ctx, season, ctx["sz"])
    # Our season, Players and Lab can be cut to a slice of games.
    if st.session_state.get("games_slice") not in D.GAME_SLICES:
        st.session_state["games_slice"] = D.GAME_SLICES[0]
    if place == "Our season":
        c, _ = st.columns([1.2, 3])
        games_slice = c.selectbox("Games", D.GAME_SLICES, key="games_slice", label_visibility="collapsed",
                                  help="Work out every card from these games only")
        ctx["team_view"], ctx["player_view"] = D.slice_games(team, ctx["player_df"], games_slice, ctx["league"])
        picks["games"] = games_slice if games_slice != D.GAME_SLICES[0] else None
        return our_season(ctx, season, baseline, D.team_season(ctx["team_view"], season),
                          D.players_season(ctx["player_view"], season), games_slice)
    if place == "Players":
        names = D.player_list(D.players_season(ctx["player_df"], season))
        if st.session_state.get("v2_player") not in names:
            st.session_state["v2_player"] = SQUAD
        player = st.session_state.get("v2_player")
        cols = st.columns([1.2, 1.2, 1, 1.6] if player != SQUAD else [1.2, 1, 3], vertical_alignment="center")
        player = cols[0].selectbox("Player", [SQUAD] + names, key="v2_player", label_visibility="collapsed")
        player = None if player == SQUAD else player
        vs = None
        if player:
            others = [n for n in names if n != player]
            if st.session_state.get("v2_vs") not in others:
                st.session_state["v2_vs"] = NOBODY
            vs = cols[1].selectbox("Compare with", [NOBODY] + others, key="v2_vs",
                                   label_visibility="collapsed")
            vs = None if vs == NOBODY else vs
        games_slice = cols[2 if player else 1].selectbox(
            "Games", D.GAME_SLICES, key="games_slice", label_visibility="collapsed",
            help="Work out every card from these games only")
        ctx["team_view"], ctx["player_view"] = D.slice_games(team, ctx["player_df"], games_slice, ctx["league"])
        picks.update(player=player, vs=vs, games=games_slice if games_slice != D.GAME_SLICES[0] else None)
        return players(ctx, season, baseline, D.players_season(ctx["player_view"], season), player, vs,
                       games_slice)
    return None
    club = st.session_state.get("v2_club")
    return lab(ctx, season, tdf, D.players_season(ctx["player_df"], season),
               None if pick in (None, SQUAD) else pick, None if club in (None, EVERY_CLUB) else club)


def dock(ctx, season, baseline, focus):
    """Phones and portrait tablets: Wharf-ai docked to the bottom of the screen,
    always in view; tap to open it over the page."""
    if st.session_state.get("pending_prompt"):
        st.session_state["wa_open"] = True
    if st.session_state.get("wa_open"):
        with st.container(key="wa_dock_open"):
            if st.button("Close Wharf-ai", key="wa_close", icon=":material/expand_more:", type="tertiary"):
                st.session_state["wa_open"] = False
                st.rerun()
            with st.container(key="card_wharfai"):
                ctx["chat_panel"](season, baseline, focus)
    else:
        with st.container(key="wa_dock"):
            if st.button("Ask Wharf-ai about this page", key="wa_open_btn", icon=":material/forum:",
                         width="stretch"):
                st.session_state["wa_open"] = True
                st.rerun()


def inject_css(dock_mode, win_h):
    st.markdown(
        f"""
        <style>
          .block-container {{ padding:0 14px {"96px" if dock_mode else "24px"} !important; }}
          /* Pages scroll, so card text wraps instead of being cut off. */
          .card-title, .card-take, .card-title .take, .cv-band .ttl, .cv-band .ttl small {{ white-space:normal !important; }}
          .cv-band.v2 {{ height:auto; min-height:56px; flex-wrap:wrap; row-gap:6px; margin:6px 0 4px; }}
          .cv-band.v2 .opt, .cv-band.v2 .opt2 {{ display:block; }}
          .cv-band.v2 .cv-stat span {{ display:block; }}
          /* Tiles fill whole rows: 6, then 3, then 2 a row as the window narrows. */
          .cv-tiles.v2 {{ grid-template-columns:repeat(6, minmax(0, 1fr)) !important; margin:6px 0; }}
          @media (max-width: 1250px) {{ .cv-tiles.v2 {{ grid-template-columns:repeat(3, minmax(0, 1fr)) !important; }} }}
          @media (max-width: 699px) {{ .cv-tiles.v2 {{ grid-template-columns:repeat(2, minmax(0, 1fr)) !important; }} }}
          .cv-tiles.v2 .fr {{ font-size:.75rem; color:var(--muted); }}
          .v2-sub {{ font-size:.78rem; font-weight:700; color:var(--muted); margin:2px 0 4px;
            text-transform:uppercase; letter-spacing:.04em; }}
          .st-key-v2_leaders {{ background:#fff; border-radius:4px; padding:10px 14px 6px; }}
          .v2-line {{ font-size:.85rem; color:var(--muted); margin:2px 0 4px; }}
          .v2-line b {{ color:var(--ink); }}
          .cv-tiles.v2 .val small {{ font-size:.7em; color:var(--muted); font-weight:600; }}
          div[data-testid="stMarkdownContainer"]:has(> .card-take),
          div[data-testid="stMarkdownContainer"]:has(> .v2-sub),
          div[data-testid="stMarkdownContainer"]:has(> .v2-line) {{ margin-bottom:0 !important; }}
          .st-key-v2_leaders .v2-sub + div {{ margin-bottom:4px; }}
          div[data-testid="stColumn"]:has(.st-key-card_wharfai) {{
            position:sticky; top:8px; align-self:flex-start; }}
          /* Docked Wharf-ai: a bar along the bottom, opening over the page. */
          .st-key-wa_dock, .st-key-wa_dock_open {{ position:fixed; left:0; right:0; bottom:0; z-index:60;
            background:#fff; padding:10px 14px calc(10px + env(safe-area-inset-bottom, 0px));
            box-shadow:0 -6px 18px rgba(26,26,26,.14); }}
          .st-key-wa_dock button {{ background:var(--brand) !important; color:#fff !important;
            border:none !important; min-height:44px; }}
          .st-key-wa_dock button p {{ color:#fff !important; font-weight:700; }}
          .st-key-wa_dock_open {{ top:12vh; overflow-y:auto; border-radius:12px 12px 0 0; }}
          .st-key-wa_dock_open .st-key-card_wharfai {{ background:#fff; }}
        </style>
        """,
        unsafe_allow_html=True)
