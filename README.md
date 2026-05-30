# PropLine Python SDK

Official Python client for the [PropLine](https://prop-line.com) player props API — real-time betting odds from Bovada, DraftKings, FanDuel, Pinnacle, Unibet, and PrizePicks across MLB, NBA, NHL, soccer, UFC, and more.

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

1. Go to [prop-line.com](https://prop-line.com)
2. Enter your email
3. Get your API key instantly — **500 requests/day, no credit card required**

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
| `prizepicks` | PrizePicks (DFS) | MLB, NBA, NHL, 9 soccer leagues — player props only; synthetic +100/+100 even-money pricing since DFS payouts scale with parlay correct-count, not per-pick odds |

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

Every odds endpoint accepts a `period=` kwarg to scope results to
first-quarter / first-half / first-period / first-N-innings markets. Omit
it for full-game markets — the default behavior is unchanged.

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

### Get game scores

```python
scores = client.get_scores("baseball_mlb")
for game in scores:
    if game["status"] == "final":
        print(f"{game['away_team']} {game['away_score']}, "
              f"{game['home_team']} {game['home_score']}")
```

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

### Get closing line / CLV (Hobby+)

One call returns the last snapshot per `(book, market, outcome)` at or
before `commence_time` — the canonical closing line for CLV tracking.

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
            print(f"{book['key']}: closed at {o['price']} ({o['closing_at']})")
            # Compare to your entry: -110 → closing -130 = +CLV
```

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

### Get player hit-rate trends (Pro full, Free redacted)

```python
# "How often has Aaron Judge gone over his total bases line lately?"
# Rolling Over/Under splits over the last 5/10/20/50 graded games,
# plus current streak and most-recent line/actual. Omit `market` for
# trends across every market the player has graded games in.
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
# Find +EV plays on a single event. Pinnacle anchors the no-vig fair
# line; every other book's price gets an EV%, with +EV plays floated
# to the top of each line group.
ev = client.get_event_ev("baseball_mlb", 12345,
    markets=["pitcher_strikeouts", "batter_hits"])

for line in ev["lines"]:
    plus = [o for o in line["outcomes"] if o["is_plus_ev"]]
    if plus:
        print(f"\n{line['market_key']} {line['description']} "
              f"line={line['point']} fair={line['fair_source']}")
        for o in plus:
            print(f"  {o['book_title']:11s} {o['name']:6s} "
                  f"{o['price']:+5d}  ev=+{o['ev_pct']}%")
```

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

## Webhooks (Streaming tier)

The Streaming tier ($79/mo) pushes `line_movement` and `resolution` events
to your URL in real time, with HMAC-SHA256 signing and automatic retries.

### Register a subscription

```python
wh = client.create_webhook(
    url="https://example.com/hooks/propline",
    filter_sport_key="baseball_mlb",
    filter_market_key="pitcher_strikeouts",
    min_price_change_pct=2.0,  # only fire on shifts of 2%+ (or any point change)
)

# Store wh["secret"] — this is the ONLY time it's returned.
SECRET = wh["secret"]
print(f"webhook id: {wh['id']}")
```

### Verify incoming deliveries

Each POST carries these headers:

| Header | Purpose |
|--------|---------|
| `X-PropLine-Event` | `line_movement`, `resolution`, or `test` |
| `X-PropLine-Timestamp` | Unix seconds |
| `X-PropLine-Signature` | HMAC-SHA256 over `f"{timestamp}." + body` |
| `X-PropLine-Delivery` | Stable delivery id (use for idempotency) |

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
  "player_name": null,
  "outcome_name": "Over",
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
  "player_name": "Tarik Skubal (DET)",
  "outcome_name": "Over",
  "point": 6.5,
  "resolution": "won",
  "actual_value": 9.0,
  "resolved_at": "2026-04-18T06:14:22Z"
}
```

### Manage subscriptions

```python
for wh in client.list_webhooks():
    print(wh["id"], wh["url"], "active" if wh["active"] else "paused")

client.update_webhook(wh_id, min_price_change_pct=5.0)  # change a filter
client.test_webhook(wh_id)                              # queue a test payload
client.list_webhook_deliveries(wh_id, limit=50)         # last 50 attempts
client.delete_webhook(wh_id)                            # cascades deliveries
```

## Error Handling

```python
from propline import PropLine, AuthError, RateLimitError, PropLineError

client = PropLine("your_api_key")

try:
    odds = client.get_odds("baseball_mlb", event_id=1)
except AuthError:
    print("Invalid API key")
except RateLimitError:
    print("Daily limit exceeded — upgrade at prop-line.com/#pricing")
except PropLineError as e:
    print(f"API error: {e.status_code} — {e.detail}")
```

## Links

- **Website**: [prop-line.com](https://prop-line.com)
- **API Docs**: [prop-line.com/docs](https://prop-line.com/docs)
- **Dashboard**: [prop-line.com/dashboard](https://prop-line.com/dashboard)
- **API Reference**: [api.prop-line.com/docs](https://api.prop-line.com/docs)

## License

MIT
