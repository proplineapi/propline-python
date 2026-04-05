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
