# Freo In Numbers: coach and analyst sessions

A script for 30-minute sessions with 2 or 3 coaches or analysts. The goal is to see where the
app helps, where people hesitate or look in the wrong place, and what they want that it
doesn't show. Watch and take notes; don't teach the app during the tasks.

Updated 11 October 2026 for the four places (Last game, Next opponent, Our season, Players)
in the purple top bar, the Games picker on Our season and Players (all, home, away,
finals, wins, losses, v top 8, last 10), momentum charts, the match simulator and its what-if
sliders, the SIMULATED ground maps, the Ask buttons on every card, and Wharf-ai always in view.

## Before the session

- Run `python evals/coach_answers.py` the day before and print its output: it works out every
  expected answer below from the data as it stands, so the answer sheet is never stale.
- One person per session, with you beside them. 30 minutes: 2 intro, 20 tasks, 8 debrief.
- Their own laptop or the screen they would really use (a laptop, the TV in the coaches' box,
  or a phone if that's how they'd look at it).
- Sign them in. Let them choose whether to take the tour ("New here?" by the ? button), and
  note which.
- Afterwards, open the Wharf-ai usage page (the chart icon next to ?, admins only) and filter to
  their session: what they asked is part of the result. It's kept in Supabase, so it's still
  there later.
- Ask if you can take notes. Say it is the app being tested, not them.

## Say at the start

"This is a draft of a performance dashboard. I'll give you seven things to find out. Think out
loud as you go: what you're looking for, what you expect to see, anything that surprises you.
There are no wrong answers. If you'd normally ask someone or give up, say so."

## The tasks

Time each task from when you finish reading it to when they give an answer. Stop at 3 minutes.
Don't help unless they're stuck for a minute; if you do, note it. Tasks 8 and 9 only if there's time.

The answers are 2026's, as of 11 October 2026; use the printout from `evals/coach_answers.py`
if the data has changed since.

| # | Task (read it out) | Expected answer (2026) | Where it is | Tests |
|---|---|---|---|---|
| 1 | "How did the season go, in one sentence?" | 21-6; minor premiers on 19-4 (137.2%); lost the grand final to Brisbane by 7, 89-96. | Our season band; Next opponent for the ladder | Warm-up: the band and the four places |
| 2 | "Why did we lose the grand final?" | Kicked 12.17 (41.4%) to Brisbane's 14.12 (53.8%) from 3 more scoring shots; won inside 50s 62-48 and clearances 45-31; led by 10 at three quarter time. | Last game (it opens on the grand final): tiles, Tale of the tape | Reading the band, tiles and tale of the tape |
| 3 | "When did the grand final turn?" | Up 17 in the last quarter, lost by 7: Brisbane kicked 4.0 unanswered. | Last game: Momentum (the shaded run) | Whether the momentum chart reads without help |
| 4 | "Which of our players had a big game in the grand final, compared with what they normally do?" | Hayden Young (9 tackles, +157%; also metres gained and pressure acts), Isaiah Dudley (5 inside 50s, 406 metres gained), Murphy Reid, Shai Bolton (686 metres gained). The tinted cells in the players table. | Last game: Show every player's numbers (the toggle under the cards) | Whether the tinted cells read as "above his own average"; sorting by a column |
| 5 | "How do we go against the top 8, and what's different in those games?" | 11-4, average margin +12.2 (+22.5 over all games). Winning the disposal count matters most against them (won 90% when ahead, 40% when behind); metres gained still tracks the margin most. | Our season, Games picker set to "vs top 8" | Finding and trusting the Games picker |
| 6 | "We play Brisbane next. What do we need to know, and what are our chances?" | 3rd, 16-7 (121.7%); top 3 for inside 50s and centre and stoppage clearances, bottom 3 for tackles and pressure acts; they win 94% when they win metres gained. Freo 2-2 against them. At a neutral ground the model gives Freo about 52% (a forecast, not data). | Next opponent (Brisbane): band, Scouting notes, Simulate | Picking a club; whether they trust, or question, the simulator |
| 7 | "The board wants one thing that decides our games. What would you tell them?" | Metres gained differential moves with the margin most (r 0.89); won 19 of 21 when ahead on it. Inside 50s next (r 0.57). Association, not cause. | Our season: What wins us games (the r column); or Wharf-ai | Whether "r" means anything to them; whether they use Ask |
| 8 | (if time) "Is Caleb Serong in form?" | 24.5 disposals a game, down 11% on 2025; last 5 at 23.6; 1st in the squad for contested possessions and clearances. | Players: Who's up, who's down, or his profile | Players: trend, squad rank |
| 9 | (if time) "What would most lift our chances against Brisbane?" | No right answer: the what-if sliders move the win chance a few points each (contested possessions most, for Adelaide). Note what they make of it. | Next opponent: the simulator's "What would change it?" section | Whether a model's what-if is useful or misleading to a coach |

After tasks 2, 5 and 7, ask: "How sure are you of that answer? Would you say it to the senior
coach?" (1 to 5).

## What to watch for

- **Where they look first.** Do they read the takeaway line under each card title, or the
  chart? Do they notice the highlighted bar or row that matches it?
- **Navigation.** Do they find the four places in the top bar and the picker beside the band?
  Do they find The squad in the Players picker?
- **The Games picker.** Do they find it for task 4 without help? Do they notice the band says
  "vs top 8 only" afterwards, and remember to set it back?
- **Clicking.** Do they try clicking charts? Do they find that any game opens Last game for it
  and any player opens their profile? Do they use the browser's Back button?
- **The players table.** Do the tinted cells read as "big game for him", or do they read the bars
  as the main thing? Do they sort by a column?
- **Hover.** Do they find the tooltips? On a touch screen, what happens when they tap?
- **Momentum and the ground maps.** Do the momentum charts make sense without the tour? Do
  they notice the ground maps are SIMULATED, or take them as real?
- **The simulator.** Do they read the win chance as a forecast? Do they try the venue switch,
  "Simulate another game" and the what-if sliders?
- **Wharf-ai.** Do they use it, and when (first, when stuck, or from a card's Ask button)? Do they trust its numbers? Do they
  open "Show the numbers", rate an answer, use the follow-ups?
- **Words they use that the app doesn't** ("stoppage", "structure", "possession chain").
- **Anything they want that isn't in the data** (shot locations, zones, positions, GPS). The app
  can't show these; note how often they come up.

## Note sheet (one per task)

```
Task #   Time (s)   Answer right? (Y / partly / N)   Helped? (Y/N)
Path taken:
Hesitated at:
Said:
Confidence (1-5):
```

## Debrief questions (8 minutes)

1. What would you use this for in a normal week? When would you open it?
2. What was the most useful thing on the screen? The least?
3. What did you look for that wasn't there?
4. Where would you use it: desk, coaches' box, the rooms, a phone?
5. Wharf-ai: would you ask it things a stats person would otherwise answer? What would make you
   trust it more?
6. If you could change one thing, what would it be?

## Afterwards

- Put each person's times and answers side by side. A task that more than one person got wrong
  or took over 2 minutes is a design problem, not a user problem.
- List every "looked for but wasn't there" and every Wharf-ai question. Recurring ones are
  candidates for a card, a view or a Wharf-ai tool.
- Run `python evals/review_feedback.py` for any thumbs-down answers from the sessions.
- Group the problems: finding things (navigation), reading things (layout, labels), trusting
  things (numbers, explanations), missing things (data or features).
- Re-run the same tasks after the next round of changes, and compare the times.
