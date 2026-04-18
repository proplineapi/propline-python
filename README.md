# PropLine Python SDK

Official Python client for the [PropLine](https://prop-line.com) player props API — real-time betting odds for MLB, NBA, NHL, and NFL.

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

## Available Markets

### MLB
`pitcher_strikeouts`, `pitcher_earned_runs`, `pitcher_hits_allowed`, `batter_hits`, `batter_home_runs`, `batter_rbis`, `batter_total_bases`, `batter_stolen_bases`, `batter_walks`, `batter_singles`, `batter_doubles`, `batter_runs`

### NBA
`player_points`, `player_rebounds`, `player_assists`, `player_threes`, `player_points_rebounds_assists`, `player_double_double`

### NHL
`player_goals`, `player_shots_on_goal`, `goalie_saves`, `player_blocked_shots`

### Game Lines (all sports)
`h2h`, `spreads`, `totals`

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

### Get game scores

```python
scores = client.get_scores("baseball_mlb")
for game in scores:
    if game["status"] == "final":
        print(f"{game['away_team']} {game['away_score']}, "
              f"{game['home_team']} {game['home_score']}")
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

### Get historical line movement (Pro only)

```python
history = client.get_odds_history("baseball_mlb", event_id=16,
    markets=["pitcher_strikeouts"])

for market in history["markets"]:
    for outcome in market["outcomes"]:
        print(f"\n{outcome['description']}:")
        for snap in outcome["snapshots"]:
            print(f"  {snap['recorded_at']}: {snap['price']} @ {snap['point']}")
```

## Webhooks (Streaming tier)

The Streaming tier ($149/mo) pushes `line_movement` and `resolution` events
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
