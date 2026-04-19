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

import hashlib
import hmac
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
            Each event has a ``bookmakers`` array with one entry per source book
            that carries lines for the requested market — currently ``bovada``,
            ``draftkings``, ``fanduel``, and ``pinnacle`` (coverage varies by
            sport and market). Iterate this array to compare prices across
            books without making separate requests.

        Example:
            >>> odds = client.get_odds("basketball_nba", event_id=21,
            ...     markets=["player_points", "player_rebounds"])
            >>> for bookmaker in odds["bookmakers"]:
            ...     print(bookmaker["key"])  # bovada, draftkings, fanduel, ...
            ...     for market in bookmaker["markets"]:
            ...         for outcome in market["outcomes"]:
            ...             print(f"  {outcome['description']} {outcome['name']} "
            ...                   f"{outcome['point']} @ {outcome['price']}")
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

    # ------------------------------------------------------------------
    # Webhooks (Streaming tier)
    # ------------------------------------------------------------------

    def create_webhook(
        self,
        url: str,
        events: list[str] | None = None,
        filter_sport_key: str | None = None,
        filter_event_id: int | None = None,
        filter_market_key: str | None = None,
        filter_player_name: str | None = None,
        min_price_change_pct: float | None = None,
    ) -> dict:
        """
        Register a webhook subscription. Streaming tier only.

        The returned dict includes the full signing ``secret`` — this is the
        ONLY time the secret is returned. Subsequent calls return a masked
        value. Store it securely.

        Args:
            url: HTTPS URL that will receive POSTed events.
            events: Event types to subscribe to. Default: all.
                Valid values: "line_movement", "resolution".
            filter_sport_key: Only deliver events for this sport
                (e.g. "baseball_mlb").
            filter_event_id: Only deliver events for this specific event.
            filter_market_key: Only deliver events for this market
                (e.g. "pitcher_strikeouts").
            filter_player_name: Case-insensitive substring match on the
                outcome's player_name.
            min_price_change_pct: Minimum % change in American odds to
                trigger a line_movement event. Point-only shifts always
                pass regardless. 0 = fire on any change.

        Returns:
            Webhook dict with full ``secret`` field (only time it's revealed).

        Example:
            >>> wh = client.create_webhook(
            ...     "https://example.com/hooks/propline",
            ...     filter_sport_key="baseball_mlb",
            ...     min_price_change_pct=5.0,
            ... )
            >>> SECRET = wh["secret"]  # store this — it won't be shown again
        """
        body: dict[str, Any] = {"url": url}
        if events is not None:
            body["events"] = events
        if filter_sport_key is not None:
            body["filter_sport_key"] = filter_sport_key
        if filter_event_id is not None:
            body["filter_event_id"] = filter_event_id
        if filter_market_key is not None:
            body["filter_market_key"] = filter_market_key
        if filter_player_name is not None:
            body["filter_player_name"] = filter_player_name
        if min_price_change_pct is not None:
            body["min_price_change_pct"] = min_price_change_pct
        return self._request("POST", "/webhooks", json=body)

    def list_webhooks(self) -> list[dict]:
        """List your webhook subscriptions. Secret is masked."""
        return self._request("GET", "/webhooks")

    def get_webhook(self, webhook_id: int) -> dict:
        """Get a single webhook subscription. Secret is masked."""
        return self._request("GET", f"/webhooks/{webhook_id}")

    def update_webhook(
        self,
        webhook_id: int,
        url: str | None = None,
        events: list[str] | None = None,
        filter_sport_key: str | None = None,
        filter_event_id: int | None = None,
        filter_market_key: str | None = None,
        filter_player_name: str | None = None,
        min_price_change_pct: float | None = None,
        active: bool | None = None,
    ) -> dict:
        """Update fields on a webhook. Only supplied fields are changed."""
        body: dict[str, Any] = {}
        if url is not None:
            body["url"] = url
        if events is not None:
            body["events"] = events
        if filter_sport_key is not None:
            body["filter_sport_key"] = filter_sport_key
        if filter_event_id is not None:
            body["filter_event_id"] = filter_event_id
        if filter_market_key is not None:
            body["filter_market_key"] = filter_market_key
        if filter_player_name is not None:
            body["filter_player_name"] = filter_player_name
        if min_price_change_pct is not None:
            body["min_price_change_pct"] = min_price_change_pct
        if active is not None:
            body["active"] = active
        return self._request("PATCH", f"/webhooks/{webhook_id}", json=body)

    def delete_webhook(self, webhook_id: int) -> dict:
        """Delete a webhook and cascade-remove its delivery history."""
        return self._request("DELETE", f"/webhooks/{webhook_id}")

    def test_webhook(self, webhook_id: int) -> dict:
        """Queue a sample ``test`` payload to the webhook's URL."""
        return self._request("POST", f"/webhooks/{webhook_id}/test")

    def list_webhook_deliveries(self, webhook_id: int, limit: int = 50) -> list[dict]:
        """
        Return recent delivery attempts for a webhook.

        Each delivery has ``status`` (pending/success/failed), ``response_code``,
        ``attempts``, ``delivered_at``, and the ``payload`` that was sent.
        """
        return self._request(
            "GET",
            f"/webhooks/{webhook_id}/deliveries",
            params={"limit": limit},
        )

    @staticmethod
    def verify_signature(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
        """
        Verify that an inbound webhook delivery was signed by PropLine.

        Use this in your receiver to authenticate requests before trusting
        their payloads. Compares HMAC-SHA256(secret, f"{timestamp}." + body)
        against the provided signature in constant time.

        Args:
            secret: The webhook's signing secret (from ``create_webhook``).
            timestamp: Value of the ``X-PropLine-Timestamp`` header.
            body: Raw request body bytes.
            signature: Value of the ``X-PropLine-Signature`` header.

        Returns:
            True if the signature matches, False otherwise.

        Example (FastAPI receiver):
            >>> @app.post("/hooks/propline")
            ... async def receive(request: Request):
            ...     body = await request.body()
            ...     ok = PropLine.verify_signature(
            ...         SECRET,
            ...         request.headers["X-PropLine-Timestamp"],
            ...         body,
            ...         request.headers["X-PropLine-Signature"],
            ...     )
            ...     if not ok:
            ...         raise HTTPException(401, "bad signature")
        """
        message = f"{timestamp}.".encode() + body
        expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
