"""
PropLine API client.

Usage:
    from propline import PropLine

    client = PropLine("your_api_key")

    # List sports
    sports = client.get_sports()

    # Get today's NBA games
    events = client.get_events("basketball_nba")

    # Get player props for a game
    odds = client.get_odds("basketball_nba", event_id=21, markets=["player_points", "player_rebounds"])

    # Get historical line movement (Pro only)
    history = client.get_odds_history("baseball_mlb", event_id=16, markets=["pitcher_strikeouts"])
"""

from __future__ import annotations

from typing import Any

import httpx


class PropLineError(Exception):
    """Base exception for PropLine API errors."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class RateLimitError(PropLineError):
    """Raised when the daily request limit is exceeded."""
    pass


class AuthError(PropLineError):
    """Raised when the API key is missing or invalid."""
    pass


class PropLine:
    """
    Client for the PropLine player props API.

    Args:
        api_key: Your PropLine API key. Get one free at https://prop-line.com
        base_url: API base URL (default: https://api.prop-line.com/v1)
        timeout: Request timeout in seconds (default: 15)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.prop-line.com/v1",
        timeout: float = 15.0,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"X-API-Key": api_key},
            timeout=httpx.Timeout(timeout),
        )

    def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = self._client.request(method, f"{self.base_url}{path}", **kwargs)

        if resp.status_code == 401:
            raise AuthError(401, resp.json().get("detail", "Invalid API key"))
        elif resp.status_code == 429:
            raise RateLimitError(429, resp.json().get("detail", "Rate limit exceeded"))
        elif resp.status_code >= 400:
            detail = resp.json().get("detail", resp.text) if resp.text else str(resp.status_code)
            raise PropLineError(resp.status_code, detail)

        return resp.json()

    def get_sports(self) -> list[dict]:
        """
        List all available sports.

        Returns:
            List of sport objects with keys: key, title, active

        Example:
            >>> client.get_sports()
            [{"key": "baseball_mlb", "title": "MLB", "active": True}, ...]
        """
        return self._request("GET", "/sports")

    def get_events(self, sport: str) -> list[dict]:
        """
        List upcoming events for a sport.

        Args:
            sport: Sport key (e.g. "baseball_mlb", "basketball_nba", "hockey_nhl", "football_nfl")

        Returns:
            List of event objects with keys: id, sport_key, home_team, away_team, commence_time

        Example:
            >>> client.get_events("basketball_nba")
            [{"id": "21", "home_team": "Cleveland Cavaliers", "away_team": "Indiana Pacers", ...}, ...]
        """
        return self._request("GET", f"/sports/{sport}/events")

    def get_odds(
        self,
        sport: str,
        event_id: int | str | None = None,
        markets: list[str] | None = None,
    ) -> dict | list[dict]:
        """
        Get current odds. If event_id is provided, returns odds for that event
        (including player props). Otherwise returns bulk odds for all events.

        Args:
            sport: Sport key (e.g. "baseball_mlb")
            event_id: Optional event ID for single-event odds with player props
            markets: List of market keys to filter by. Defaults vary by endpoint.
                Common markets:
                - Game lines: "h2h", "spreads", "totals" (includes alt lines + team totals)
                - MLB props: "pitcher_strikeouts", "pitcher_outs", "batter_hits",
                  "batter_home_runs", "batter_rbis", "batter_total_bases",
                  "batter_2plus_hits", "batter_2plus_home_runs", "batter_2plus_rbis",
                  "batter_3plus_rbis" (includes alt lines automatically)
                - NBA props: "player_points", "player_rebounds", "player_assists",
                  "player_threes", "player_steals", "player_blocks", "player_turnovers"
                - NHL props: "player_goals", "player_shots_on_goal", "goalie_saves"
                - Soccer props: "anytime_goal_scorer", "first_goal_scorer",
                  "both_teams_to_score", "2plus_goals", "player_assists",
                  "player_cards", "goal_or_assist", "total_corners", "total_cards"

        Returns:
            Single event odds dict (if event_id provided) or list of event odds dicts.

        Example:
            >>> odds = client.get_odds("basketball_nba", event_id=21,
            ...     markets=["player_points", "player_rebounds"])
            >>> for bookmaker in odds["bookmakers"]:
            ...     for market in bookmaker["markets"]:
            ...         for outcome in market["outcomes"]:
            ...             print(f"{outcome['description']} {outcome['name']} {outcome['point']}")
        """
        params = {}
        if markets:
            params["markets"] = ",".join(markets)

        if event_id is not None:
            return self._request("GET", f"/sports/{sport}/events/{event_id}/odds", params=params)
        else:
            return self._request("GET", f"/sports/{sport}/odds", params=params)

    def get_markets(self, sport: str, event_id: int | str) -> list[dict]:
        """
        List available market types for a specific event.

        Useful for discovering what props are available before requesting odds.

        Args:
            sport: Sport key (e.g. "baseball_mlb")
            event_id: Event ID

        Returns:
            List of dicts with keys: key (market key), outcomes_count (number of outcomes)

        Example:
            >>> markets = client.get_markets("baseball_mlb", event_id=51)
            >>> for m in markets:
            ...     print(f"{m['key']}: {m['outcomes_count']} outcomes")
            # pitcher_strikeouts: 4 outcomes
            # batter_hits: 36 outcomes
        """
        return self._request("GET", f"/sports/{sport}/events/{event_id}/markets")

    def get_odds_history(
        self,
        sport: str,
        event_id: int | str,
        markets: list[str] | None = None,
    ) -> dict:
        """
        Get historical odds movement for an event.

        Pro tier returns full snapshot history. Free tier returns market
        structure with snapshot counts (redacted=True, snapshots_available=N)
        and an upgrade_url.

        Args:
            sport: Sport key
            event_id: Event ID
            markets: List of market keys to filter by

        Returns:
            Event dict with markets containing timestamped snapshots showing
            how odds moved over time. Free tier: snapshots array is empty
            but snapshots_available shows how many exist.

        Example:
            >>> history = client.get_odds_history("baseball_mlb", event_id=16,
            ...     markets=["pitcher_strikeouts"])
            >>> for market in history["markets"]:
            ...     for outcome in market["outcomes"]:
            ...         print(f"{outcome['description']}: {len(outcome['snapshots'])} changes")
            ...         for snap in outcome["snapshots"]:
            ...             print(f"  {snap['recorded_at']}: {snap['price']} @ {snap['point']}")
        """
        params = {}
        if markets:
            params["markets"] = ",".join(markets)

        return self._request(
            "GET", f"/sports/{sport}/events/{event_id}/odds/history", params=params
        )

    def get_scores(
        self,
        sport: str,
        days_from: int = 3,
    ) -> list[dict]:
        """
        Get game scores and status for recent events.

        Args:
            sport: Sport key (e.g. "baseball_mlb")
            days_from: Number of days back to include (default: 3)

        Returns:
            List of score dicts with keys: id, sport_key, home_team, away_team,
            commence_time, status (upcoming/in_progress/final), home_score, away_score

        Example:
            >>> scores = client.get_scores("baseball_mlb")
            >>> for game in scores:
            ...     if game["status"] == "final":
            ...         print(f"{game['away_team']} {game['away_score']}, "
            ...               f"{game['home_team']} {game['home_score']}")
        """
        return self._request(
            "GET", f"/sports/{sport}/scores", params={"days_from": days_from}
        )

    def get_stats(
        self,
        sport: str,
        event_id: int | str,
        stat_type: list[str] | None = None,
    ) -> dict:
        """
        Get actual player/team stats from box scores (book-agnostic).

        Returns raw stat values that can be used to resolve props against
        any sportsbook's lines — not tied to any specific book.

        Args:
            sport: Sport key (e.g. "soccer_epl", "baseball_mlb")
            event_id: Event ID
            stat_type: Optional list of stat types to filter by.
                Common types:
                - MLB: "strikeouts", "hits", "home_runs", "total_bases", "rbis"
                - NBA: "points", "rebounds", "assists", "threes", "steals"
                - NHL: "goals", "shots_on_goal", "saves"
                - Soccer: "goals", "assists", "shots_on_target", "corners", "cards"

        Returns:
            Event dict with status, scores, and a stats array. Each stat has:
            player_name, team_abbr, stat_type, stat_value.

        Example:
            >>> stats = client.get_stats("soccer_epl", event_id=1147)
            >>> for s in stats["stats"]:
            ...     if s["stat_type"] == "goals" and s["stat_value"] > 0:
            ...         print(f"{s['player_name']}: {s['stat_value']} goals")
        """
        params = {}
        if stat_type:
            params["stat_type"] = ",".join(stat_type)

        return self._request(
            "GET", f"/sports/{sport}/events/{event_id}/stats", params=params
        )

    def get_results(
        self,
        sport: str,
        event_id: int | str,
        markets: list[str] | None = None,
    ) -> dict:
        """
        Get resolved prop outcomes with actual player stats.

        Pro tier returns full resolution data. Free tier returns the market
        structure with odds and lines visible but resolution/actual_value
        redacted (null, redacted=True) plus an upgrade_url.

        Args:
            sport: Sport key
            event_id: Event ID
            markets: Optional list of market keys to filter by

        Returns:
            Event dict with status, scores, and markets containing resolved
            outcomes. Pro: resolution, actual_value, resolved_at populated.
            Free: those fields are null with redacted=True.

        Example:
            >>> results = client.get_results("baseball_mlb", event_id=16,
            ...     markets=["pitcher_strikeouts", "batter_hits"])
            >>> print(f"{results['away_team']} {results['away_score']}, "
            ...       f"{results['home_team']} {results['home_score']}")
            >>> for market in results["markets"]:
            ...     for outcome in market["outcomes"]:
            ...         print(f"{outcome['description']} {outcome['name']} "
            ...               f"{outcome['point']}: {outcome['resolution']} "
            ...               f"(actual: {outcome['actual_value']})")
        """
        params = {}
        if markets:
            params["markets"] = ",".join(markets)

        return self._request(
            "GET", f"/sports/{sport}/events/{event_id}/results", params=params
        )

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
