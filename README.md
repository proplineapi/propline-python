# PropLine Python SDK

Official Python client for the [PropLine](https://prop-line.com/?ref=pypi) player props API — real-time betting odds from Bovada, DraftKings, FanDuel, Pinnacle, Unibet, and PrizePicks across MLB, NBA, NHL, soccer, UFC, and more.

## Installation

```bash
pip install propline
```

## Quick Start

```python
from propline import PropLine

client = PropLine("your_api_key")

# List available sports
sports = client.get_sports()
# [{"key": "baseball_mlb", "title": "MLB", "active": True}, ...]

# Get today's NBA games
events = client.get_events("basketball_nba")
for event in events:
    print(f"{event['away_team']} @ {event['home_team']}")

# Get player props for a game
odds = client.get_odds("basketball_nba", event_id=events[0]["id"],
    markets=["player_points", "player_rebounds", "player_assists"])

for bookmaker in odds["bookmakers"]:
    for market in bookmaker["markets"]:
        for outcome in market["outcomes"]:
            print(f"{outcome['description']} {outcome['name']} "
                  f"{outcome['point']} @ {outcome['price']}")
```

## Get Your API Key

1. Go to [prop-line.com](https://prop-line.com/?ref=pypi)
2. Enter your email
3. Get your API key instantly — **1,000 requests/day, no credit card required**

## Available Sports

| Key | Sport |
|-----|-------|
| `baseball_mlb` | MLB |
| `basketball_nba` | NBA |
| `basketball_ncaab` | College Basketball |
| `football_ncaaf` | College Football |
| `golf` | Golf |
| `tennis` | Tennis |
| `hockey_nhl` | NHL |
| `football_nfl` | NFL |
| `soccer_epl` | EPL |
| `soccer_la_liga` | La Liga |
| `soccer_serie_a` | Serie A |
| `soccer_bundesliga` | Bundesliga |
| `soccer_ligue_1` | Ligue 1 |
| `soccer_mls` | MLS |
| `mma_ufc` | UFC |
| `boxing` | Boxing |

> **Migrating from the-odds-api?** Their sport key names work as aliases (`americanfootball_nfl`, `icehockey_nhl`, `soccer_spain_la_liga`, `mma_mixed_martial_arts`, ...) so only the base URL changes. Aliases exist only where the competition is identical; anything else returns a structured 404 with `did_you_mean` rather than a silently-different feed.


## Bookmakers

Every odds response returns a `bookmakers` array so you can compare lines
across books in a single request — iterate the array to line-shop.

| Key | Book | Coverage |
|-----|------|----------|
| `bovada` | Bovada | All 19 sports — game lines + full player props |
| `draftkings` | DraftKings | MLB, NBA, NHL, 6 soccer leagues — game lines + player props |
| `fanduel` | FanDuel | MLB, NBA, NHL, 6 soccer leagues — game lines + player props |
| `pinnacle` | Pinnacle | MLB (game lines + props), NBA/NHL/soccer (game lines, goalie saves) |
| `unibet` | Unibet | MLB/NBA/NHL + 6 soccer leagues — game lines; NBA + NHL + soccer player props (points, rebounds, assists, threes, steals, blocks, PRA, shots on goal, goalscorer, cards, BTTS, total corners) |
| `prizepicks` | PrizePicks (DFS) | MLB, NBA, WNBA, NHL, tennis, UFC, soccer — player props only; synthetic +100/+100 even-money pricing since DFS payouts scale with parlay correct-count, not per-pick odds. Each outcome carries `dfs_odds_type` (`standard` = the market line, `goblin` = easier/lower-payout, `demon` = harder/higher-payout). Filter to `standard` for the market line; goblin/demon arrive as their own per-line markets (e.g. `Points (demon 27.5)`). Each goblin/demon outcome also carries `line_gap` — the signed delta from that player+stat's standard line (`+demon` harder / `-goblin` easier; null when no standard counterpart) |
| `underdog` | Underdog Fantasy (DFS) | MLB, NBA, NHL, tennis, UFC, 9 soccer leagues — player props with real two-way American prices and a `payout_multiplier` on every outcome (`1.0` = standard pick; e.g. `1.5` boost / `0.75` discount; `None` only means the book is not Underdog). Keep only `payout_multiplier == 1.0` when comparing DFS lines to sportsbook consensus — filtering on non-null would drop every Underdog line |

```python
from propline import PropLine, Bookmaker

client = PropLine("your_api_key")

odds = client.get_odds("baseball_mlb", event_id=events[0]["id"],
    markets=["pitcher_strikeouts"])

# Filter to a specific book
for bk in odds["bookmakers"]:
    if bk["key"] == Bookmaker.DRAFTKINGS:
        ...

# Or iterate all books
for bk in odds["bookmakers"]:
    print(f"\n{bk['title']}")
    for market in bk["markets"]:
        for o in market["outcomes"]:
            print(f"  {o['description']} {o['name']} {o['point']}: {o['price']}")
# Bovada
#   Zack Wheeler Over 6.5: -130
# DraftKings
#   Zack Wheeler Over 6.5: -125
# FanDuel
#   Zack Wheeler Over 6.5: -135
```

## Available Markets

### MLB
`pitcher_strikeouts`, `pitcher_outs`, `pitcher_earned_runs`, `pitcher_hits_allowed`, `batter_hits`, `batter_home_runs`, `batter_rbis`, `batter_total_bases`, `batter_stolen_bases`, `batter_walks`, `batter_singles`, `batter_doubles`, `batter_runs`, `batter_2plus_hits`, `batter_2plus_home_runs`, `batter_2plus_rbis`, `batter_3plus_rbis`

### NBA
`player_points`, `player_rebounds`, `player_assists`, `player_threes`, `player_steals`, `player_blocks`, `player_turnovers`, `player_points_rebounds`, `player_points_assists`, `player_rebounds_assists`, `player_points_rebounds_assists`, `player_double_double`, `player_triple_double`

### NHL
`player_goals`, `player_first_goal`, `player_goals_2plus`, `player_goals_3plus`, `player_shots_on_goal`, `player_points_1plus`, `player_points_2plus`, `player_points_3plus`, `goalie_saves`, `player_blocked_shots`

### Soccer (EPL, La Liga, Serie A, Bundesliga, Ligue 1, MLS)
`anytime_goal_scorer`, `first_goal_scorer`, `2plus_goals`, `goal_or_assist`, `player_assists`, `player_2plus_assists`, `player_cards`, `both_teams_to_score`, `double_chance`, `draw_no_bet`, `correct_score`, `total_corners`, `total_cards`

### UFC / Boxing
`h2h`, `total_rounds`, `fight_distance`, `round_betting`

### Game Lines (all sports)
`h2h`, `spreads`, `totals` (includes alt lines and team totals)

A **team total** rides the same `totals` key as the game total, so one book can
return several `totals` markets on one event. Read the market's `team` field to
tell them apart — it carries the canonical event team name (matching
`home_team` / `away_team` exactly) on a team total and is `None` on the game
total:

```python
game_total = next(m for m in book["markets"]
                  if m["key"] == "totals" and m.get("team") is None)
```

`team` is always `None` outside `totals`, and is present on odds, odds history,
closing lines and movement. The book's own `description` is still there as the
human-readable label, but every book words it differently (Bovada suffixes
`" - {team}"`, BetUS prefixes `"Team Total - "`, Smarkets and TAB say nothing),
so prefer `team` over parsing that string.

## Examples

### Get MLB pitcher strikeout props

```python
from propline import PropLine

client = PropLine("your_api_key")

events = client.get_events("baseball_mlb")
for event in events:
    odds = client.get_odds("baseball_mlb", event_id=event["id"],
        markets=["pitcher_strikeouts"])

    print(f"\n{event['away_team']} @ {event['home_team']}")
    for bk in odds["bookmakers"]:
        for mkt in bk["markets"]:
            for o in mkt["outcomes"]:
                if o["point"]:
                    print(f"  {o['description']} {o['name']} {o['point']}: {o['price']}")
```

### Filter to game-period markets

Every odds endpoint (`get_odds`, `get_odds_history`, `get_odds_closing`,
`get_movement`) also accepts a `bookmakers=` kwarg — a bookmaker key or
list of keys, same parameter name as the-odds-api — to restrict the
response to specific books:

```python
# Only DraftKings + FanDuel lines
odds = client.get_odds(
    "baseball_mlb", event_id=12345,
    markets=["pitcher_strikeouts"],
    bookmakers=["draftkings", "fanduel"],
)
```

Every odds endpoint accepts a `period=` kwarg to scope results to
first-quarter / first-half / first-period / first-N-innings markets. Omit
it for full-game markets — the default behavior is unchanged.

### Event-page links (click out to the book)

`get_odds` and `get_event_best_line` accept `include_links=True` — each
bookmaker block (odds) or price row (best-line) then carries a `link`:
that book's public event-page URL, so your UI can click out from a line
straight to the book. Plain navigation, no affiliate tagging. Links ship
for Bovada, DraftKings, FanDuel, BetMGM, Kalshi, Polymarket and
Smarkets; other books return `None`. The same flag also adds `app_link`
— a mobile app-open deep link that opens the book's native app on the
fixture (app-store fallback otherwise), vs `link` = the desktop web page.
ProphetX only today; `None` elsewhere.

```python
bl = client.get_event_best_line(
    "baseball_mlb", 12345, include_links=True)
for line in bl["lines"]:
    for side, info in line["sides"].items():
        best = info["best"]
        print(f"{side}: {best['price']} @ {best['book_title']} -> {best['link']}")
```

### Native book ids (join onto a book's own data)

`get_odds` accepts `include_book_ids=True` — each bookmaker block then
carries a `book_event_id` and each outcome a `book_outcome_id`: that
book's OWN identifiers for the event and the priced selection. Use them
to join PropLine rows onto a book's native feed by id, instead of
fuzzy-matching team names, player names and lines.

Kalshi ships both — the event ticker and the per-contract market ticker
— which makes this the leg-level join key if you already pull Kalshi's
own API. Most other books ship an event id; books without a stable
public id return `None`.

```python
event = client.get_odds(
    "baseball_mlb", event_id=12345,
    markets=["h2h"],
    include_book_ids=True,
)
for book in event["bookmakers"]:
    print(book["key"], book["book_event_id"])
    for m in book["markets"]:
        for o in m["outcomes"]:
            print("   ", o["name"], o["book_outcome_id"])
```

Note a two-sided market can share **one** `book_outcome_id` across both
legs: a Kalshi contract is binary, so Over and Under are its YES and NO
sides. The id identifies the contract; the outcome's `name` tells you
which side.

```python
# First-quarter NBA totals
q1 = client.get_odds(
    "basketball_nba", event_id=12345,
    markets=["totals"],
    period="q1",   # q1|q2|q3|q4 | h1|h2 | p1|p2|p3 | i1..i9 | f3|f5|f7
)

# Multiple periods in one call — pass a list or a comma-separated string
both = client.get_odds(
    "basketball_nba", event_id=12345,
    markets=["totals"],
    period=["q1", "q2"],
)

# Pass period="all" to include every period alongside the full-game row.
```

Every response row carries a `period` field so you can bucket
client-side. Coverage today: Bovada / DraftKings / FanDuel / Pinnacle on
NBA / NHL / MLB / soccer. Football period markets land at NFL preseason
(August 2026). The same `period=` kwarg works on `get_odds_history()` and
`get_odds_closing()` too.

### Exchange liquidity (is the price actually bettable?)

ProphetX is a peer-to-peer exchange, so its best price is often a thin
dangling offer with only a few dollars behind it. Every ProphetX outcome
carries `liquidity` — the dollars you can actually stake at the quoted
price — so you can filter or flag quotes that are only good for a buck.
`None` for books without a resting-size signal. The same field rides
every price row on `get_best_line`, where a thin exchange quote often
wins the best slot on price alone.

```python
event = client.get_odds("baseball_mlb", event_id=12345)
for book in event["bookmakers"]:
    if book["key"] != "prophetx":
        continue
    for m in book["markets"]:
        for o in m["outcomes"]:
            liq = o.get("liquidity")
            if liq is not None and liq < 25:
                print(f"thin: {m['key']} {o['name']} {o['price']} (${liq})")
```

### Get game scores

```python
scores = client.get_scores("baseball_mlb")
for game in scores:
    if game["status"] == "final":
        print(f"{game['away_team']} {game['away_score']}, "
              f"{game['home_team']} {game['home_score']}")
```

### Get game context — pitchers, umpire, weather (free)

```python
ctx = client.get_context("baseball_mlb", event_id=37464)
print(f"{ctx['away_probable_pitcher']} ({ctx['away_probable_pitcher_hand']}) @ "
      f"{ctx['home_probable_pitcher']} ({ctx['home_probable_pitcher_hand']})")
print(f"Umpire: {ctx['home_plate_umpire']}  Lineup set: {ctx['lineup_confirmed']}")
if ctx["weather"]:
    w = ctx["weather"]
    print(f"{w['temperature_f']}F, wind {w['wind_speed_mph']}mph {w['wind_direction']}, {w['conditions']}")
```

The conditions a prop settles under. For MLB: probable starting pitchers
and their throwing hand (`home_probable_pitcher_hand` /
`away_probable_pitcher_hand`, "L"/"R"/"S" — platoon-split context for every
batter prop), a confirmed-lineup flag, the home-plate umpire, and
first-pitch weather at outdoor / open-roof venues. For NFL & NCAAF: the
venue and kickoff weather (pitcher/umpire/lineup fields are `None` for
football). The same block is embedded in `get_results()`, so every graded
prop carries its conditions — unique to PropLine. Free tier. Raises on
`404` when no context is on file for the event yet.

### Get line movement & steam (Hobby+)

```python
mv = client.get_movement("baseball_mlb", event_id=37464)
for s in mv["steam"]:
    print(f"{s['name']} {s['consensus_direction']} "
          f"({s['books_moved']}/{s['books_quoting']} books, score {s['steam_score']})")
```

Line movement derived from our snapshot tick history. Per (book, market,
outcome): opening line, latest line, implied-probability + point shift,
direction. The `steam` array flags outcomes multiple books moved the same
direction — the sharp-money signal across every book we poll. Unique to
PropLine. Hobby+ full; free tier redacted.

### Get resolution coverage summary (free)

```python
s = client.get_resolution_summary(days=30)
print(f"{s['total_graded']:,} props graded across "
      f"{s['sports_covered']} sports in {s['days']}d")
for row in s["by_sport"][:5]:
    print(f"  {row['title']}: {row['graded']:,} ({row['events']} games)")
```

### Get resolved prop outcomes (Pro only)

```python
results = client.get_results("baseball_mlb", event_id=16,
    markets=["pitcher_strikeouts", "batter_hits"])

print(f"{results['away_team']} {results['away_score']}, "
      f"{results['home_team']} {results['home_score']}")

for market in results["markets"]:
    for outcome in market["outcomes"]:
        print(f"{outcome['description']} {outcome['name']} "
              f"{outcome['point']}: {outcome['resolution']} "
              f"(actual: {outcome['actual_value']})")
# Output: "Tarik Skubal (DET) Over 6.5: won (actual: 7.0)"
```

### Get historical line movement (Hobby+)

```python
history = client.get_odds_history("baseball_mlb", event_id=16,
    markets=["pitcher_strikeouts"])

for book in history["bookmakers"]:
    for market in book["markets"]:
        for outcome in market["outcomes"]:
            print(f"\n[{book['key']}] {outcome['description']}:")
            for snap in outcome["snapshots"]:
                print(f"  {snap['recorded_at']}: {snap['price']} @ {snap['point']}"
                      f" (book reported: {snap.get('book_updated_at') or 'n/a'})")
```

Each snapshot carries up to three change-detection signals:
`recorded_at` (when our scraper saw the odds), `book_updated_at` (when
the book itself reports the price was last set — Bovada today),
and `book_version` (per-market monotonic counter — Pinnacle today).
The gap between `recorded_at` and `book_updated_at` is per-book
scraper latency; deltas in `book_version` between two snapshots tell
you how many distinct market updates the book recorded between them,
even when the visible price didn't change. See
<https://prop-line.com/docs#timestamps> for the full semantic.

#### Period-historical query params

Combine any of these to scope, downsample, and de-noise:

```python
# Just the last 30 minutes of moves before tip — and only the moments
# when the line actually changed.
moves = client.get_odds_history(
    "baseball_mlb", event_id=16,
    markets=["pitcher_strikeouts"],
    relative_from="-30m",
    relative_to="0",
    changes_only=True,
)

# One snapshot per minute for the 3 hours before commence — stable
# spacing for backtests / moving averages.
ts = client.get_odds_history(
    "baseball_mlb", event_id=16,
    markets=["pitcher_strikeouts"],
    relative_from="-3h",
    relative_to="0",
    interval="1m",   # 30s | 1m | 5m | 15m | 30m | 1h
)
```

- `from` / `to`: absolute ISO timestamps (`from_` in Python — `from` is reserved).
- `relative_from` / `relative_to`: offsets relative to `commence_time`. Forms: `-3h`, `-30m`, `-90s`, `0`. Mutually exclusive with the absolute counterpart.
- `interval`: downsample to one snapshot per bucket; latest snapshot in each bucket wins.
- `changes_only`: drop adjacent snapshots whose `(price, point)` match the previous one. Opening line is always kept.

### Get opening & closing lines / CLV (Hobby+)

One call returns **both ends of the move** per `(book, market, outcome)`:
the last snapshot at or before `commence_time` (`price` / `point` /
`closing_at`) and the first snapshot in the same 14-day pre-kickoff window
(`opening_price` / `opening_point` / `opening_at`).

```python
closing = client.get_odds_closing(
    "baseball_mlb", event_id=5885,
    markets=["pitcher_strikeouts"],
)

for book in closing["bookmakers"]:
    for m in book["markets"]:
        for o in m["outcomes"]:
            if o["description"] != "Bryan Woo" or o["name"] != "Over":
                continue
            print(f"{book['key']}: opened {o['opening_price']} @ {o['opening_point']}"
                  f" -> closed {o['price']} @ {o['point']} ({o['closing_at']})")
            # Compare to your entry: -110 → closing -130 = +CLV
```

Compare the **points**, not just the prices. On spreads and totals the
number moves as much as the price (6.5 → 7.0), so a price-only comparison
silently mis-measures those markets.

`opening_age_seconds` is how long before kickoff the opener was recorded.
The archive starts April 2026, so for a book/sport PropLine began polling
after a line was posted, `opening_*` means *first observed by us* rather
than the book's true open — a value in minutes rather than hours is the
tell.

### Grade your bets against the close (Hobby+)

`get_odds_closing` gives you the closing line; `grade_clv` does the whole
job — send the bets you actually placed and get CLV, the de-vigged closing
fair, and the graded result back per bet. Stateless: nothing is stored.

```python
res = client.grade_clv([
    {
        "ref": "b1",
        "sport_key": "baseball_mlb",
        "event_id": 150791,
        "market": "batter_hits_runs_rbis",
        "bookmaker": "lowvig",
        "selection": "Drake Baldwin",
        "side": "Under",
        "point": 0.5,
        "price": 145,
        "stake": 1,
    },
])

s = res["summary"]
print(f"{s['matched']}/{s['bets']} matched · "
      f"beat the close {s['beat_close_pct']}% · {s['profit_units']:+.2f}u")

for b in res["bets"]:
    if not b["matched"]:
        print(f"{b['ref']}: unmatched ({b['unmatched_reason']})")
        continue
    print(f"{b['ref']}: took {b['price']} vs close {b['closing_price']} "
          f"-> CLV {b['clv_pct']:+.2f}% · "
          f"vs de-vigged close {b['ev_vs_close_pct']:+.2f}% "
          f"({b['fair_source']}) -> {b['resolution']}")
```

**Two CLV numbers, and they disagree on purpose.** `clv_pct` is
price-vs-price: familiar and quotable, but vig-blind, so it flatters a bet
taken on the juicy side of a wide market. `ev_vs_close_pct` scores your
price against the **de-vigged** close and is the honest one — a -110 taken
into a -105/-115 close beat the price but not the fair line. On a real bet
the two came out +6.52% and +0.08%.

The de-vig uses the **sharpest book quoting that line at close**
(`fair_source`), not the book you bet at — de-vigging your own book always
returns a negative number, because you paid its hold.

Bets whose event hasn't started carry `closing_is_final: False`, land in
`summary["pending"]`, and are **excluded from the averages**: before
kickoff the "closing" price is just the latest price, so CLV is ~0 by
construction.

Matching is **fail-closed**. A bet that can't be pinned to exactly one
stored outcome comes back `matched: False` with an `unmatched_reason`
(`event_not_found`, `no_market_for_key`, `no_outcome_for_selection`,
`ambiguous_selection`, `no_closing_snapshot`) rather than a confident
wrong match. Lines match by equality, never nearest-value — 0.5 and 1.5
are different bets. Max 500 bets per request.

### Price a same-game parlay at the book's own odds (Hobby+)

`price_sgp` returns the book's **own correlated price** for a slip — what a
FanDuel customer would be offered for it right now — beside the independent
product of the single-leg prices and their ratio.

```python
q = client.price_sgp("baseball_mlb", 150791, [
    {"market": "h2h", "name": "St. Louis Cardinals"},
    {"market": "batter_1plus_hits", "name": "Freddie Freeman",
     "description": "Freddie Freeman"},
])
print(q["quoted"], q["sgp_price"], q["independent_price"], q["correlation_factor"])
# True 592 322 1.6387
```

Legs are named exactly as `/odds` names an outcome (or by `book_outcome_id`
from `includeBookIds=True`). Matching is fail-closed: a leg that does not pin
to exactly one stored outcome raises a 422 naming the leg. `quoted: False`
means the book will not offer that combination as a same-game parlay; refused
legs carry the book's own `failure_code`. Books: `fanduel`, `betonlineag`, `lowvig`.

### Get player prop history (Pro full, Free redacted)

```python
# "Did Bryan Woo go over/under his last 10 strikeout props?"
hist = client.get_player_history("baseball_mlb", "Bryan Woo",
    market="pitcher_strikeouts", limit=10)

for e in hist["entries"]:
    print(f"{e['commence_time'][:10]} {e['bookmaker_title']}: "
          f"line {e['line']}, actual {e['actual_value']} "
          f"-> Over {e['over_result']}, Under {e['under_result']}")
# Output: "2026-04-19 DraftKings: line 6.5, actual 6.0 -> Over lost, Under won"
```

### Get a player's game log / head-to-head (free)

```python
# Every raw box-score stat, per game, in one call — no fanning out one
# request per event. Build L5/L10/L20, season splits and charts from these.
log = client.get_player_games("baseball_mlb", "Aaron Judge", limit=10)

for g in log["games"]:
    where = "vs" if g["is_home"] else "@"
    print(f"{g['commence_time'][:10]} {where} {g['opponent']}: "
          f"{g['stats'].get('hits', 0)} H, {g['stats'].get('home_runs', 0)} HR")

# Head-to-head — accepts a name, nickname or abbreviation. The limit applies
# AFTER the filter, so this is the last 5 MEETINGS, not the Boston games
# among his last 5 games. Not capped to the current season.
h2h = client.get_player_games("baseball_mlb", "Aaron Judge",
    limit=5, opponent="BOS")
```

This reads the raw-stats archive, not graded-prop history — it covers every
game with a box score on file, including games no sportsbook priced, so a
"last 10 games" window here really is the last 10 games. It carries no line,
price or grade; use `get_player_trends` for hit rates against a posted line.

### Get player hit-rate trends (Pro full, Free redacted)

```python
# "How often has Aaron Judge gone over his total bases line lately?"
# Rolling Over/Under splits over the last 5/10/20/50 graded games,
# plus current streak and most-recent line/actual. Omit `market` for
# trends across every market the player has graded games in. Pass
# `dfs_odds_type="standard"|"goblin"|"demon"` to compute the trend
# against that PrizePicks flavor's line only.
trends = client.get_player_trends("baseball_mlb", "Aaron Judge",
    market="batter_total_bases")

for m in trends["markets"]:
    l10 = m["last_10"]
    streak = m["current_streak"]
    print(f"{m['market']}: line {m['recent_line']}, avg {m['avg_actual']}, "
          f"L10 {l10['over']}-{l10['under']} ({l10['over_pct']}% over), "
          f"streak {streak['length']} {streak['result']}")
# Output: "batter_total_bases: line 1.5, avg 2.02, L10 3-7 (30.0% over), streak 2 under"
```

### Cross-book +EV (Pro)

```python
# Find +EV plays on a single event. A sharp book anchors the no-vig
# fair line; every other book's price gets an EV%, with +EV plays
# floated to the top of each line group.
#
# `bookmakers` narrows the PRICES to books you hold accounts at — never
# the anchor. This still measures DK and FD against Pinnacle. Read
# line["fair_source"] to see which book anchored each line; the anchor
# is picked per line, so one response mixes several.
ev = client.get_event_ev("baseball_mlb", 12345,
    markets=["pitcher_strikeouts", "batter_hits"],
    bookmakers=["draftkings", "fanduel"])  # optional

for line in ev["lines"]:
    plus = [o for o in line["outcomes"] if o["is_plus_ev"]]
    if plus:
        print(f"\n{line['market_key']} {line['description']} "
              f"line={line['point']} fair={line['fair_source']}")
        for o in plus:
            print(f"  {o['book_title']:11s} {o['name']:6s} "
                  f"{o['price']:+5d}  ev=+{o['ev_pct']}%")
```

### Market-implied projections (Hobby+)

```python
# The statistical value the market implies per (market, player) — the
# line where the no-vig P(over) crosses 50%, median across books.
# Market-implied arithmetic, not a forecast. Use it to validate your
# own projections against the live market.
proj = client.get_event_projections("football_nfl", 25070,
    markets=["player_pass_yds", "player_receptions"])  # optional

for row in proj["projections"]:
    print(f"{row['player']:24s} {row['market_key']:22s} "
          f"proj={row['projected_value']}  "
          f"books={row['books_contributing']}")
```

### Best line — cross-book line shopping (Hobby+)

```python
# You've decided the bet — now find which book pays the most.
bl = client.get_event_best_line("baseball_mlb", 12345,
    markets="pitcher_strikeouts",
    bookmakers=["draftkings", "fanduel", "bovada"])  # only my books

for line in bl["lines"]:
    for side, info in line["sides"].items():
        best = info["best"]
        print(f"{line['description']:24s} {side:6s} {line['point']}: "
              f"{best['price']:+5d} @ {best['book_title']} "
              f"(of {len(info['all_prices'])} books)")
```

DFS pick'em books (PrizePicks, Sleeper, Dabble) are excluded — their
quotes aren't independently bettable payouts; Underdog is included only
at clean two-way lines. Each price carries `last_update` so you can
discount stale quotes.

### Bulk CSV export of resolved props (Pro)

```python
# Save every resolved MLB strikeout prop since April 1st to disk.
client.export_resolved_props(
    sport="baseball_mlb",
    market="pitcher_strikeouts",
    since="2026-04-01T00:00:00Z",
    out_path="./mlb-strikeouts.csv",
)

# Or parse in memory with pandas for analysis.
import io
import pandas as pd
data = client.export_resolved_props(sport="baseball_mlb")
df = pd.read_csv(io.BytesIO(data))
hit_rate = (df.query("outcome_name == 'Over' and resolution == 'won'").shape[0]
            / df.query("outcome_name == 'Over'").shape[0])
print(f"Over hit rate across all MLB markets: {hit_rate:.1%}")
```

Every row carries **both ends of the line move** alongside the graded
result — `opening_price` / `opening_point` / `opening_at` (first line in
the 14 days before kickoff) and `closing_price` / `closing_point` /
`closing_at` (last line at or before it) — so a full CLV study is one
download rather than one `/odds/closing` call per event:

```python
df = pd.read_csv(io.BytesIO(data))
df = df[df.closing_price.notna() & df.opening_price.notna()]
# Did the market move toward the Over after it opened?
moved_to_over = df.query("outcome_name == 'Over' and closing_price < opening_price")
print(moved_to_over.groupby("market").resolution.value_counts(normalize=True))
```

`closing_point` is distinct from `line` (the outcome's own current point);
on spreads and totals they differ whenever the number moved. New columns
are always appended immediately before `customer_token`, so positional
parsers written against an earlier column set keep working.

### Full line-movement history (Historical Backfill / Enterprise)

```python
# Every recorded snapshot (price + line, per book) — not just the close.
# The raw tick history no subscription tier can bulk-pull; exclusive to
# the one-time Historical Backfill pass and Enterprise. Page month by
# month — a full archive runs to gigabytes per sport.
client.export_odds_history(
    sport="baseball_mlb",
    since="2026-04-01T00:00:00Z",
    until="2026-05-01T00:00:00Z",
    out_path="./mlb-line-history-apr.csv",
)
```

## Webhooks (Streaming tier)

The Streaming tiers push `line_movement`, `resolution`, `steam` and
`market_suspended` events to your URL in real time, with HMAC-SHA256 signing
and automatic retries.

### Register a subscription

```python
wh = client.create_webhook(
    url="https://example.com/hooks/propline",
    filter_sport_key="baseball_mlb",
    filter_market_key="pitcher_strikeouts",
    min_price_change_pct=2.0,  # only fire on shifts of 2%+ (or any point change)
    batch_max=100,             # recommended: up to 100 events per POST
)

# Store wh["secret"] — this is the ONLY time it's returned.
SECRET = wh["secret"]
print(f"webhook id: {wh['id']}")
```

With `batch_max` set (1–500), events arrive as a signed envelope instead of
one POST each: `{"batch": true, "event_type": ..., "count": N, "events":
[{"delivery_id": ..., "data": <per-event payload>}, ...]}` with an
`X-PropLine-Batch: N` header. Dedupe on each element's `delivery_id`. Use it
for any high-volume subscription — sport-wide `line_movement` can exceed
1,000 events/min during a full slate, and one POST per event caps your
delivery rate at your endpoint's response time. `batch_max=0` reverts to
per-event delivery. JSON format only (Discord stays per-event).

### Verify incoming deliveries

Each POST carries these headers:

| Header | Purpose |
|--------|---------|
| `X-PropLine-Event` | `line_movement`, `resolution`, `steam`, `market_suspended`, or `test` |
| `X-PropLine-Timestamp` | Unix seconds |
| `X-PropLine-Signature` | HMAC-SHA256 over `f"{timestamp}." + body` |
| `X-PropLine-Delivery` | Stable delivery id (use for idempotency) |
| `X-PropLine-Sequence` | Your subscription's own event counter (use for replay) |

```python
from propline import PropLine

# In a FastAPI/Flask handler:
ok = PropLine.verify_signature(
    secret=SECRET,
    timestamp=headers["X-PropLine-Timestamp"],
    body=raw_body_bytes,
    signature=headers["X-PropLine-Signature"],
)
if not ok:
    return 401
```

### Line-movement payload

```json
{
  "event_type": "line_movement",
  "sport_key": "baseball_mlb",
  "event": {"id": 5070, "home_team": "Seattle Mariners", "away_team": "Texas Rangers", ...},
  "market_key": "totals",
  "market_description": "Total 7.5",
  "player_name": null,
  "outcome_name": "Over",
  "dfs_odds_type": null,
  "payout_multiplier": null,
  "previous": {"price_american": -750, "point": 7.0},
  "current":  {"price_american": -300, "point": 7.5},
  "price_change_pct": 60.0,
  "timestamp": "2026-04-18T03:49:00Z"
}
```

### Resolution payload

```json
{
  "event_type": "resolution",
  "sport_key": "baseball_mlb",
  "event": {"id": 16, "home_score": 4, "away_score": 2, "status": "final", ...},
  "market_key": "pitcher_strikeouts",
  "market_description": "Total Pitching Strikeouts",
  "player_name": "Tarik Skubal (DET)",
  "outcome_name": "Over",
  "dfs_odds_type": null,
  "payout_multiplier": null,
  "point": 6.5,
  "resolution": "won",
  "actual_value": 9.0,
  "resolved_at": "2026-04-18T06:14:22Z"
}
```

`market_description` is where a DFS alt market's flavor + line live (e.g.
PrizePicks `"Rebounds (demon 12.5)"`). `dfs_odds_type` is the PrizePicks
flavor (`standard` / `goblin` / `demon`; null for every traditional book);
`payout_multiplier` is Underdog's numeric boost/discount (PrizePicks
publishes no numeric multiplier — the flavor is the signal). Same semantics
as the identically-named fields on `/odds` outcomes.

### Market-suspended payload

### Stale prices on a live game (`pregame_only`)

Each bookmaker block in `/odds` carries `pregame_only`. It is `True` when the
event is **live** and that book does not price it in play — the prices shown
are its last pregame quote and will not move again until the game ends.

This is the one staleness case `suspended_at` cannot show you: that flag is set
when a book *pulls* a market, and a book with no in-play feed is never polled
for the fixture once it starts, so nothing goes missing and nothing is flagged.

```python
odds = client.get_event_odds("football_ncaaf", event_id)
live_books = [b for b in odds["bookmakers"] if not b.get("pregame_only")]
```

The rows are still returned rather than withheld, because on the DFS books that
frozen pregame line is the number the bet settles against — so treat
`pregame_only: true` as "a real price, but not a live one".

A book took a market off the board pregame. One delivery per (book, event,
player) — a late scratch is ONE event carrying every key the book pulled, not
one per key. `books_agreeing` is how many books have pulled the same subject
on the same event; subscribe with `min_books_agreeing=3` to hear only
corroborated drops, or leave it unset to hear every one (the right choice if
you price off a single book). Pull-side twin: `suspended_at` on every market
in `/odds`, on every tier.

```python
client.create_webhook(
    url="https://example.com/hooks/propline",
    events=["market_suspended"],
    filter_sport_key="baseball_mlb",
    min_books_agreeing=3,   # omit to receive every single-book drop
)
```

```json
{
  "event_type": "market_suspended",
  "sport_key": "baseball_mlb",
  "event": {"id": 138811, "home_team": "Pittsburgh Pirates", "away_team": "Boston Red Sox", ...},
  "bookmaker_key": "draftkings",
  "bookmaker_title": "DraftKings",
  "subject": "Willson Contreras",
  "reason": "off_the_board",
  "markets": [
    {"key": "batter_hits", "description": "Willson Contreras Hits O/U", "period": null,
     "last_seen": "2026-08-16T14:03:45+00:00",
     "last_price": [{"name": "Over", "price": -115, "point": 0.5},
                    {"name": "Under", "price": -105, "point": 0.5}]},
    {"key": "batter_total_bases", "...": "..."}
  ],
  "books_agreeing": 7,
  "books": ["betmgm", "betrivers", "draftkings", "novig", "pinnacle", "prophetx", "underdog"],
  "suspended_at": "2026-08-16T14:07:30+00:00"
}
```

`reason` is `"off_the_board"` for a sportsbook and `"no_offers"` for an
exchange whose resting offers went. There is no restore event: when the
market returns, `line_movement` fires on the returning price.

### Manage subscriptions

```python
for wh in client.list_webhooks():
    print(wh["id"], wh["url"], "active" if wh["active"] else "paused")

client.update_webhook(wh_id, min_price_change_pct=5.0)  # change a filter
client.test_webhook(wh_id)                              # queue a test payload
client.list_webhook_deliveries(wh_id, limit=50)         # newest 50 attempts
client.list_webhook_deliveries(wh_id, limit=200, before_id=123456)  # page backwards
client.delete_webhook(wh_id)                            # cascades deliveries
```

### Catching up after an outage

Every delivery carries `X-PropLine-Sequence` — a counter that is monotonic
*within your subscription*. Store the highest one you have processed, then read
forward from it. Do not use `X-PropLine-Delivery` as the cursor: that id is
global across all subscriptions, so gaps in it are other customers' traffic.

```python
cursor = load_my_cursor()          # highest X-PropLine-Sequence you processed

while True:
    page = client.replay_webhook_events(wh_id, since_seq=cursor, limit=100)

    if page["truncated"]:
        # Events after your cursor aged out of retention and are gone.
        # Resync from the REST endpoints rather than assume you are current.
        resync_from_rest()

    for ev in page["events"]:      # oldest first
        handle(ev["event_type"], ev["data"])

    cursor = page["next_seq"]
    save_my_cursor(cursor)
    if not page["has_more"]:
        break

print("behind by", page["latest_seq"] - cursor, "events")
```

### Websocket streaming

If your system already speaks websockets — or you simply can't host a public
HTTPS endpoint — connect a socket instead of receiving POSTs. Same events, same
filters, same `seq`: a stream and a webhook are the **same subscription with a
different transport**, so they cannot deliver you different things.

```bash
pip install propline[stream]
```

```python
wh = client.create_webhook(
    transport="websocket",          # no url — there is nowhere to POST
    events=["line_movement"],
    filter_sport_key="baseball_mlb",
)

async for ev in client.stream(wh["id"], since_seq=my_cursor):
    handle(ev["event_type"], ev["data"])
    my_cursor = ev["seq"]           # persist it; this is your resume point
```

It reconnects and resumes from the last `seq` automatically, so a dropped
connection is not a gap in your data. Pass `on_truncated=...` to be told when
events after your cursor aged out of retention — the one case streaming cannot
make you whole, where you should resync from REST.

Concurrent connections are capped per plan (Streaming Lite 2, Streaming 5).
Delivered events are **not** metered.

Replay is bounded by delivery retention: 2 days, and at most 5,000 deliveries
per subscription. `latest_seq` is not subject to retention, so
`latest_seq - next_seq` stays honest even after the rows are pruned. Sequence
numbers always increase and never repeat but are **not** guaranteed to be
dense — treat a skipped number as normal and read `truncated` for real loss.
Neither `replay_webhook_events` nor `list_webhook_deliveries` counts against
your daily quota.

## Error Handling

```python
from propline import PropLine, AuthError, RateLimitError, PropLineError

client = PropLine("your_api_key")

try:
    odds = client.get_odds("baseball_mlb", event_id=1)
except AuthError:
    print("Invalid API key")
except RateLimitError as e:
    # Daily-cap 429s include a pre-filled one-click upgrade URL
    print(f"Rate limited: {e.message}")
    if e.upgrade_url:
        print(f"Upgrade: {e.upgrade_url}")
except PropLineError as e:
    print(f"API error: {e.status_code} — {e.message}")
```

Gated and throttled endpoints return a structured error body
([docs](https://prop-line.com/docs?ref=pypi#errors)); its fields are exposed as
attributes on every `PropLineError`:

| Attribute | Meaning |
|---|---|
| `error_code` | Stable machine-readable code: `upgrade_required`, `daily_limit_exceeded`, `burst_limit_exceeded`, `missing_api_key`, `invalid_api_key` (None on plain errors) |
| `message` | Human-readable sentence (also `str(err)`) |
| `required_tier` | Cheapest tier that unlocks a gated feature (403s) |
| `upgrade_url` | Where to unlock it — pre-filled one-click URL on daily-cap 429s |
| `retry_after_seconds` | Burst-limit backoff hint (429s) |
| `detail` | The raw API value — dict when structured, str otherwise |

## Tracking Your Usage

Every authenticated response carries live quota headers; the client parses
them into `client.last_quota` automatically:

```python
client.get_sports()

q = client.last_quota
print(f"{q.used}/{q.limit} used today, {q.remaining} left")
print(f"Quota resets at {q.reset_at.isoformat()}")  # 00:00 UTC, hard reset
```

`last_quota` is `None` before the first request and refreshes on every call
(including 429s), so a long-running poller can watch `remaining` and back
off before hitting the daily cap.

## Links

- **Website**: [prop-line.com](https://prop-line.com/?ref=pypi)
- **API Docs**: [prop-line.com/docs](https://prop-line.com/docs?ref=pypi)
- **Recipes** (code for common jobs): [prop-line.com/recipes](https://prop-line.com/recipes?ref=pypi)
- **Odds API by sport and market** (live line, books, graded hit rate): [prop-line.com/odds-api](https://prop-line.com/odds-api?ref=pypi)
- **Prop resolution** (every prop graded against the box score): [prop-line.com/prop-resolution-api](https://prop-line.com/prop-resolution-api?ref=pypi)
- **Cross-book +EV**: [prop-line.com/ev](https://prop-line.com/ev?ref=pypi)
- **Pricing**: [prop-line.com/pricing](https://prop-line.com/pricing?ref=pypi)
- **Dashboard**: [prop-line.com/dashboard](https://prop-line.com/dashboard)
- **OpenAPI reference**: [api.prop-line.com/docs](https://api.prop-line.com/docs)
- **Node SDK**: [`npm install propline`](https://www.npmjs.com/package/propline)
- **MCP server**: [`npx -y propline-mcp`](https://www.npmjs.com/package/propline-mcp)

## License

MIT
