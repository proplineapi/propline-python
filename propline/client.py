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

    # Get a player's recent resolved prop history (Pro full, Free redacted)
    hist = client.get_player_history("baseball_mlb", "Bryan Woo", market="pitcher_strikeouts")
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx


@dataclass(frozen=True)
class QuotaStatus:
    """Live daily-quota state, parsed from the ``X-Daily-*`` headers the API
    returns on every authenticated response.

    Attributes:
        limit: Your tier's daily request cap.
        used: Requests used today (including the request that produced this).
        remaining: Requests left before the cap.
        reset_epoch: Unix seconds when the quota resets (00:00 UTC — a hard
            reset, not a rolling window).
    """

    limit: int
    used: int
    remaining: int
    reset_epoch: int

    @property
    def reset_at(self) -> datetime:
        """Quota reset time as a timezone-aware UTC datetime."""
        return datetime.fromtimestamp(self.reset_epoch, tz=timezone.utc)


class PropLineError(Exception):
    """Base exception for PropLine API errors.

    Gated and throttled endpoints return a structured ``detail`` object
    (see https://prop-line.com/docs#errors). When present, its fields are
    exposed as attributes so callers can branch on ``error_code`` and
    follow ``upgrade_url`` instead of parsing prose:

    - ``error_code``: stable machine-readable code, e.g. ``"upgrade_required"``,
      ``"daily_limit_exceeded"``, ``"burst_limit_exceeded"``, ``"invalid_api_key"``
    - ``message``: the human-readable sentence (also used as ``str(err)``)
    - ``required_tier``: cheapest tier that unlocks a gated feature
    - ``upgrade_url``: where to unlock it (pre-filled for daily-cap 429s)
    - ``retry_after_seconds``: burst-limit backoff hint
    - ``detail``: the raw value the API returned (dict when structured,
      str on older/plain errors) — unchanged for backwards compatibility
    """

    def __init__(self, status_code: int, detail):
        self.status_code = status_code
        self.detail = detail
        if isinstance(detail, dict):
            self.error_code = detail.get("error")
            self.message = detail.get("message") or str(detail)
            recommended = detail.get("recommended") or {}
            self.upgrade_url = detail.get("upgrade_url") or recommended.get("upgrade_url")
            self.required_tier = detail.get("required_tier")
            self.retry_after_seconds = detail.get("retry_after_seconds")
        else:
            self.error_code = None
            self.message = str(detail)
            self.upgrade_url = None
            self.required_tier = None
            self.retry_after_seconds = None
        super().__init__(f"[{status_code}] {self.message}")


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
        #: Daily-quota state from the most recent API response, or ``None``
        #: before the first request. Updated on every call (including 429s):
        #:     >>> client.get_sports()
        #:     >>> client.last_quota.remaining
        #:     999
        self.last_quota: QuotaStatus | None = None
        self._client = httpx.Client(
            headers={"X-API-Key": api_key},
            timeout=httpx.Timeout(timeout),
        )

    def _capture_quota(self, resp: httpx.Response) -> None:
        """Record the X-Daily-* quota headers when present (absent on
        unauthenticated errors, e.g. an invalid key's 401)."""
        try:
            self.last_quota = QuotaStatus(
                limit=int(resp.headers["X-Daily-Limit"]),
                used=int(resp.headers["X-Daily-Used"]),
                remaining=int(resp.headers["X-Daily-Remaining"]),
                reset_epoch=int(resp.headers["X-Daily-Reset"]),
            )
        except (KeyError, ValueError):
            pass

    def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = self._client.request(method, f"{self.base_url}{path}", **kwargs)
        self._capture_quota(resp)

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
        period: str | list[str] | None = None,
        bookmakers: str | list[str] | None = None,
        include_links: bool = False,
        include_book_ids: bool = False,
    ) -> dict | list[dict]:
        """
        Get current odds. If event_id is provided, returns odds for that event
        (including player props). Otherwise returns bulk odds for all events.

        Args:
            sport: Sport key (e.g. "baseball_mlb")
            event_id: Optional event ID for single-event odds with player props
            bookmakers: Optional bookmaker key(s) to restrict the response to
                (e.g. ``"draftkings"`` or ``["draftkings", "fanduel"]``).
                Omitted = all books. Same parameter name as the-odds-api.
            include_links: When True, each bookmaker block carries a
                ``link`` — that book's public event-page URL (plain
                navigation, no affiliate tagging), so your UI can click
                out from a line to the book. Links ship for Bovada,
                DraftKings, FanDuel, BetMGM, Kalshi, Polymarket and
                Smarkets; other books return ``None``. Maps to the
                the-odds-api-compatible ``includeLinks=true`` query param.
                The same flag also adds ``app_link`` — a mobile app-open
                deep link (opens the book's native app on the fixture,
                app-store fallback otherwise); ProphetX only today, ``None``
                elsewhere.
            include_book_ids: When True, each bookmaker block carries a
                ``book_event_id`` and each outcome a ``book_outcome_id`` —
                that book's OWN identifiers for the event and the priced
                selection. Use these to join PropLine rows onto a book's
                native feed by id instead of matching on team names,
                players and lines. Kalshi ships both (the event ticker
                and the per-contract market ticker, e.g.
                ``KXMLBGAME-26AUG08NYYBOS-NYY``); most other books ship
                an event id. Books without a stable id return ``None``.

                Note a two-sided market can share ONE ``book_outcome_id``
                across both legs — a Kalshi contract is binary, so Over
                and Under are its YES and NO sides. The id identifies the
                contract; the outcome's ``name`` says which side.

                PropLine-specific (``includeBookIds=true``); the-odds-api
                has no equivalent.
            markets: List of market keys to filter by. If omitted, the
                bulk /odds endpoint defaults to ``h2h`` and the per-event
                /odds endpoint defaults to ``h2h,spreads,totals`` —
                game-line markets every book carries across every sport.
                Pass an explicit list to fetch player props (sport-
                specific keys; see below).

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
            ``draftkings``, ``fanduel``, ``pinnacle``, ``unibet``, and
            ``prizepicks`` (coverage varies by sport and market). Iterate this
            array to compare prices across books without making separate
            requests.

            Underdog Fantasy outcomes carry an extra ``payout_multiplier``
            key — a DFS boost/discount factor. Every Underdog outcome
            carries a value (``None`` means the book is not Underdog). A
            standard pick is ``1.0`` (the quoted ``price`` carries the full
            payout); any other float, such as ``1.5`` (boost) or ``0.75``
            (discount), marks a "special". Keep only
            ``payout_multiplier == 1.0`` when comparing DFS lines to
            sportsbook consensus so a scaled payout doesn't read as a
            mispriced edge — filtering on non-null instead would drop every
            Underdog line.

            PrizePicks outcomes carry ``dfs_odds_type`` instead — the
            projection flavor: ``"standard"`` (the true market line),
            ``"goblin"`` (easier line / lower payout) or ``"demon"`` (harder
            line / higher payout); ``None`` for traditional sportsbooks.
            Filter to ``"standard"`` to get PrizePicks's market line —
            goblin/demon variants arrive as their own per-line markets (e.g.
            ``"Points (demon 27.5)"``) so they never overwrite it. PrizePicks
            publishes no numeric multiplier for these. Each goblin/demon
            outcome also carries ``line_gap`` — the signed delta from that
            player+stat's standard line (``point - standard_point``; positive
            on a harder demon line, negative on an easier goblin line; ``None``
            when there's no standard counterpart). Flavor + ``line_gap`` are
            the modelable signals for fitting per-pick payout adjustments.

            Every outcome also carries ``last_change_at`` — PropLine's
            observed timestamp of the last time that outcome's price actually
            changed. Unlike ``book_updated_at`` (the book's own publish-time,
            Bovada-only), ``last_change_at`` is populated for every book,
            including Pinnacle and PrizePicks. Compare it across books in a
            single call to detect repricing lag (e.g. Pinnacle just moved but
            a slower book's ``last_change_at`` is older) without a separate
            ``get_odds_history`` call per event.

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
        if period is not None:
            params["period"] = period if isinstance(period, str) else ",".join(period)
        if bookmakers:
            params["bookmakers"] = (
                bookmakers if isinstance(bookmakers, str) else ",".join(bookmakers)
            )
        if include_links:
            params["includeLinks"] = "true"
        if include_book_ids:
            params["includeBookIds"] = "true"

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
        from_: str | None = None,
        to: str | None = None,
        relative_from: str | None = None,
        relative_to: str | None = None,
        interval: str | None = None,
        changes_only: bool = False,
        period: str | list[str] | None = None,
        bookmakers: str | list[str] | None = None,
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
            from_: ISO timestamp; only include snapshots at or after this time.
                Mutually exclusive with relative_from.
            to: ISO timestamp; only include snapshots at or before this time.
                Mutually exclusive with relative_to.
            relative_from: Offset relative to commence_time, e.g. "-3h", "-30m",
                "-90s". Mutually exclusive with from_.
            relative_to: Offset relative to commence_time, e.g. "-1m" or "0"
                for commence_time itself. Mutually exclusive with to.
            interval: Downsample to one snapshot per bucket. One of "30s",
                "1m", "5m", "15m", "30m", "1h". Last snapshot in each bucket wins.
            changes_only: When True, drop snapshots whose (price, point) match
                the previous one. The opening line is always kept.

        Returns:
            Event dict with markets containing timestamped snapshots showing
            how odds moved over time. Free tier: snapshots array is empty
            but snapshots_available shows how many exist.

        Example:
            >>> # Last 30 minutes of moves before tip, change-only:
            >>> history = client.get_odds_history(
            ...     "baseball_mlb", event_id=16,
            ...     markets=["pitcher_strikeouts"],
            ...     relative_from="-30m", relative_to="0",
            ...     changes_only=True,
            ... )
        """
        params: dict[str, str | bool] = {}
        if markets:
            params["markets"] = ",".join(markets)
        if from_ is not None:
            params["from"] = from_
        if to is not None:
            params["to"] = to
        if relative_from is not None:
            params["relative_from"] = relative_from
        if relative_to is not None:
            params["relative_to"] = relative_to
        if interval is not None:
            params["interval"] = interval
        if changes_only:
            params["changes_only"] = "true"
        if period is not None:
            params["period"] = period if isinstance(period, str) else ",".join(period)
        if bookmakers:
            params["bookmakers"] = (
                bookmakers if isinstance(bookmakers, str) else ",".join(bookmakers)
            )

        return self._request(
            "GET", f"/sports/{sport}/events/{event_id}/odds/history", params=params
        )

    def get_odds_closing(
        self,
        sport: str,
        event_id: int | str,
        markets: list[str] | None = None,
        period: str | list[str] | None = None,
        bookmakers: str | list[str] | None = None,
    ) -> dict:
        """
        Get the opening and closing line per (book, market, outcome).

        Closing is the last snapshot at or before commence_time
        (``price`` / ``point`` / ``closing_at``); opening is the first
        snapshot in the same 14-day pre-kickoff window (``opening_price``
        / ``opening_point`` / ``opening_at``). Together they replace the
        "fetch full history → grep for the first and last pre-game rows"
        pattern with one call.

        Compare the *points* as well as the prices: on spreads and totals
        the number moves as much as the price (6.5 → 7.0), so a price-only
        comparison mis-measures those markets.

        ``opening_age_seconds`` is how long before kickoff the opener was
        recorded. The archive starts April 2026, so for a book/sport
        PropLine began polling after a line was posted, ``opening_*`` means
        *first observed by us* rather than the book's true open — a value
        in minutes rather than hours is the tell.

        Hobby+ tiers get full data; free tier sees market structure with
        ``redacted=True`` and an ``upgrade_url``.

        Args:
            sport: Sport key
            event_id: Event ID
            markets: List of market keys to filter by
                (default: h2h,spreads,totals)

        Returns:
            Event dict with one row per outcome carrying its closing
            ``price`` / ``point`` / ``closing_at`` and its
            ``opening_price`` / ``opening_point`` / ``opening_at``.

        Example:
            >>> closing = client.get_odds_closing(
            ...     "baseball_mlb", event_id=5885,
            ...     markets=["pitcher_strikeouts"],
            ... )
            >>> for book in closing["bookmakers"]:
            ...     for m in book["markets"]:
            ...         for o in m["outcomes"]:
            ...             print(book["key"], o["description"], o["name"],
            ...                   o["opening_price"], "@", o["opening_point"],
            ...                   "->", o["price"], "@", o["point"])
        """
        params: dict[str, str] = {}
        if markets:
            params["markets"] = ",".join(markets)
        if period is not None:
            params["period"] = period if isinstance(period, str) else ",".join(period)
        if bookmakers:
            params["bookmakers"] = (
                bookmakers if isinstance(bookmakers, str) else ",".join(bookmakers)
            )

        return self._request(
            "GET", f"/sports/{sport}/events/{event_id}/odds/closing", params=params
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

    def get_dfs_payouts(
        self,
        platform: str = "prizepicks",
        leg_win_prob: float | None = None,
    ) -> dict:
        """
        Get the PrizePicks Power/Flex payout schedule + per-leg breakeven.

        Returns the entry payout schedule for 2-6 legs of each play type
        (power = all legs must hit; flex = partial payouts) plus the per-leg
        win probability needed to break even on each.

        Args:
            platform: DFS platform. Only "prizepicks" is available today.
            leg_win_prob: Optional assumed per-leg win probability in [0, 1].
                When supplied, each play also carries ``expected_return``
                (per $1 staked) and ``is_plus_ev`` at that rate.

        Returns:
            Dict with keys: ``platform``, ``leg_win_prob``, ``disclaimer``,
            and ``plays`` (a list of {play_type, legs, all_correct_multiplier,
            payouts, breakeven_leg_win_prob[, expected_return, is_plus_ev]}).

        Note:
            These are PrizePicks's *standard* published payouts. demon/goblin
            picks adjust an entry's payout per-pick and are NOT in PrizePicks's
            feed, so they are not reflected here. Breakeven assumes independent
            legs. See the ``disclaimer`` field on the response.

        Example:
            >>> tbl = client.get_dfs_payouts(leg_win_prob=0.58)
            >>> for play in tbl["plays"]:
            ...     print(play["play_type"], play["legs"],
            ...           "breakeven", play["breakeven_leg_win_prob"])
        """
        params: dict = {"platform": platform}
        if leg_win_prob is not None:
            params["leg_win_prob"] = leg_win_prob
        return self._request("GET", "/dfs/payouts", params=params)

    def get_mlb_grand_salami(
        self,
        date: str | None = None,
    ) -> dict:
        """
        Get the synthetic MLB Grand Salami for a given UTC date — total
        runs scored across every MLB game on the slate, plus each book's
        implied Grand Salami line (median of per-game primary totals
        across our MLB books).

        No retail sportsbook quotes this as a single market, so historical
        cross-book Grand Salami data isn't available elsewhere.

        Args:
            date: YYYY-MM-DD UTC date. Defaults to today (UTC).

        Returns:
            Dict with: sport_key, date, games_total, games_completed,
            games_in_progress, games_upcoming, actual_total_runs (null
            until at least one game completes), bookmakers (list of
            {key, title, games_priced, line, result}). `result` is
            'over' / 'under' / 'push' once the slate has cleared, null
            until then.

        Example:
            >>> gs = client.get_mlb_grand_salami(date="2026-05-21")
            >>> print(f"Actual total runs: {gs['actual_total_runs']}")
            >>> for book in gs["bookmakers"]:
            ...     print(f"{book['title']}: line={book['line']} → {book['result']}")
        """
        params = {}
        if date:
            params["date"] = date
        return self._request(
            "GET", "/sports/baseball_mlb/grand-salami", params=params
        )

    def get_nhl_daily_goals_total(
        self,
        date: str | None = None,
    ) -> dict:
        """
        Get the synthetic NHL Daily Goals Total for a given UTC date —
        total goals scored across every NHL game on the slate (incl.
        OT/SO), plus each book's implied Daily Goals Total line (median
        of per-game primary totals across our NHL books).

        Hockey's equivalent of the MLB Grand Salami. No retail sportsbook
        quotes this as a single market, so historical cross-book data
        isn't available elsewhere.

        Args:
            date: YYYY-MM-DD UTC date. Defaults to today (UTC).

        Returns:
            Dict with: sport_key, date, games_total, games_completed,
            games_in_progress, games_upcoming, actual_total_goals (null
            until at least one game completes), bookmakers (list of
            {key, title, games_priced, line, result}). `result` is
            'over' / 'under' / 'push' once the slate has cleared, null
            until then.

        Example:
            >>> dgt = client.get_nhl_daily_goals_total(date="2026-05-24")
            >>> print(f"Actual total goals: {dgt['actual_total_goals']}")
            >>> for book in dgt["bookmakers"]:
            ...     print(f"{book['title']}: line={book['line']} → {book['result']}")
        """
        params = {}
        if date:
            params["date"] = date
        return self._request(
            "GET", "/sports/hockey_nhl/daily-goals-total", params=params
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

        Live during games for major US sports (MLB + WNBA now; NFL, NCAAF,
        NBA, NHL at season start): while the event's status is
        "in_progress", stats refresh roughly every 90 seconds with
        cumulative in-game values — treat them as partial until status
        flips to "final". Other sports populate stats at game completion.

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

    def get_context(
        self,
        sport: str,
        event_id: int | str,
    ) -> dict:
        """
        Get game context — the conditions a prop settles under.

        For MLB: probable starting pitchers and their throwing hand
        (``home_probable_pitcher_hand`` / ``away_probable_pitcher_hand`` —
        "L"/"R"/"S", the platoon-split context behind every batter prop), a
        confirmed-lineup flag, the home-plate umpire, and first-pitch weather
        (temperature, wind, precipitation, conditions) for outdoor / open-roof
        venues. For NFL & NCAAF: the venue and kickoff weather (the
        pitcher/umpire/lineup fields are ``None`` for football). Indoor
        or domed venues return ``weather=None`` with ``is_indoor=True``.
        The same context is embedded in :meth:`get_results`, so every
        graded prop carries the conditions it settled against — unique to
        PropLine. Free tier.

        Args:
            sport: Sport key (e.g. "baseball_mlb")
            event_id: Event ID

        Returns:
            A context dict: event_id, sport_key, home_team, away_team,
            commence_time, venue, roof_type, is_indoor,
            home_probable_pitcher, away_probable_pitcher,
            home_probable_pitcher_hand, away_probable_pitcher_hand,
            lineup_confirmed, home_plate_umpire, weather, updated_at.

        Raises:
            PropLineError: 404 when no context is on file for the event yet
            (before the context loop reaches it, or for sports without a
            context source).

        Example:
            >>> ctx = client.get_context("baseball_mlb", event_id=37464)
            >>> print(ctx["home_probable_pitcher"], "vs", ctx["away_probable_pitcher"])
            >>> if ctx["weather"]:
            ...     w = ctx["weather"]
            ...     print(f"{w['temperature_f']}F, wind {w['wind_speed_mph']}mph {w['wind_direction']}")
        """
        return self._request(
            "GET", f"/sports/{sport}/events/{event_id}/context"
        )

    def get_movement(
        self,
        sport: str,
        event_id: int | str,
        markets: list[str] | None = None,
        period: str | None = None,
        bookmakers: str | list[str] | None = None,
    ) -> dict:
        """
        Get line movement + steam detection from the snapshot tick history.

        For each (book, market, outcome) returns the opening line, the latest
        line, the signed implied-probability shift (positive = the book
        shortened the outcome / money moved toward it), the point shift, and
        a direction. The top-level ``steam`` array flags outcomes that
        multiple books moved in the same direction — the sharp-money signal,
        computed across every book PropLine polls. Unique to PropLine
        (pull-only APIs can't produce it). Hobby+ full; free tier redacted.

        Args:
            sport: Sport key (e.g. "baseball_mlb")
            event_id: Event ID
            markets: Optional list of market keys (default h2h, spreads, totals)
            period: Optional game-period filter ("q1", "h1", "p1", "f5", "all")

        Returns:
            A dict with ``bookmakers`` (per-book/market/outcome movement) and
            ``steam`` (detected steam moves with ``steam_score``). When a book
            moves the line itself, that outcome's ``prob_shift`` is null and
            ``direction`` is ``"line_moved"`` (excluded from the steam signal).

        Example:
            >>> mv = client.get_movement("baseball_mlb", 37464)
            >>> for s in mv["steam"]:
            ...     print(f"{s['name']} {s['consensus_direction']} "
            ...           f"({s['books_moved']}/{s['books_quoting']} books, "
            ...           f"score {s['steam_score']})")
        """
        params: dict[str, str] = {}
        if markets:
            params["markets"] = ",".join(markets)
        if period:
            params["period"] = period
        if bookmakers:
            params["bookmakers"] = (
                bookmakers if isinstance(bookmakers, str) else ",".join(bookmakers)
            )

        return self._request(
            "GET", f"/sports/{sport}/events/{event_id}/movement", params=params
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

    def get_player_history(
        self,
        sport: str,
        player_name: str,
        market: str,
        bookmaker: str | None = None,
        limit: int = 20,
    ) -> dict:
        """
        Get a player's recent resolved prop history for a given market.

        One entry per (event, bookmaker) pair with line + Over/Under prices
        + resolution + actual value. Use this to answer "did X go over/under
        in their last N games?" without reconstructing it from raw outcomes.

        Pro tier returns full data. Free tier returns event structure with
        resolution/actual_value/prices nulled and ``redacted=True``.

        Args:
            sport: Sport key (e.g. "baseball_mlb").
            player_name: Player's name. Case-insensitive prefix match —
                "Bryan Woo" and "bryan woo" both work, and team suffixes
                like "(SEA)" in the outcome description are tolerated.
            market: Market key (e.g. "pitcher_strikeouts", "player_points").
            bookmaker: Optional single-book filter (e.g. "draftkings"). If
                omitted, returns entries across every book that quoted lines.
            limit: Max entries to return (1-100). Default 20.

        Returns:
            Dict with keys: player_name, sport_key, market, entries, upgrade_url.
            Each entry: event_id, commence_time, home_team, away_team,
            bookmaker, bookmaker_title, line, over_price, under_price,
            actual_value, over_result, under_result, resolved_at, redacted.

        Example:
            >>> hist = client.get_player_history("baseball_mlb", "Bryan Woo",
            ...     market="pitcher_strikeouts", limit=10)
            >>> for e in hist["entries"]:
            ...     print(f"{e['commence_time'][:10]} {e['bookmaker']}: "
            ...           f"line {e['line']}, actual {e['actual_value']} "
            ...           f"-> Over {e['over_result']}")
        """
        params: dict[str, Any] = {"market": market, "limit": limit}
        if bookmaker:
            params["bookmaker"] = bookmaker

        return self._request(
            "GET",
            f"/sports/{sport}/players/{player_name}/history",
            params=params,
        )

    def get_player_trends(
        self,
        sport: str,
        player_name: str,
        market: str | None = None,
        dfs_odds_type: str | None = None,
    ) -> dict:
        """
        Get a player's hit-rate trends across recent graded games.

        For each market, returns rolling Over/Under splits over the last
        5/10/20/50 games, the current streak, the most recent line + actual
        value, and the average actual stat. Use this to answer "how often
        has X gone over their line lately?" without reconstructing it from
        raw resolved history.

        Paid tier returns full data. Free tier returns each market with only
        ``market`` + ``games_graded`` and ``redacted=True``.

        Args:
            sport: Sport key (e.g. "baseball_mlb").
            player_name: Player's name. Case-insensitive prefix match —
                "Aaron Judge" and "aaron judge" both work, and team suffixes
                like "(NYY)" in the outcome description are tolerated.
            market: Optional market key (e.g. "batter_total_bases",
                "player_points"). If omitted, returns trends for every market
                the player has graded games in.
            dfs_odds_type: Optional PrizePicks pick-em flavor — "standard",
                "goblin", or "demon". When set, the trend is computed against
                that flavor's PrizePicks line only (e.g. compare a player's
                goblin-line hit-rate against his standard-line trend). Omitted
                gives the default cross-book behavior. Flavor tagging began
                2026-06-16, so per-flavor trends only have depth from then on.

        Returns:
            Dict with keys: player_name, sport_key, dfs_odds_type (echo of the
            filter, or None), markets, upgrade_url.
            Each market entry: market, games_graded, reference_bookmaker,
            reference_bookmaker_title, recent_line, avg_actual, last_5,
            last_10, last_20, last_50, current_streak, last_game, redacted.
            Each window (last_N) — possibly null when too few games exist —
            has: window, games, over, under, push, over_pct.

        Example:
            >>> trends = client.get_player_trends("baseball_mlb", "Aaron Judge",
            ...     market="batter_total_bases")
            >>> for m in trends["markets"]:
            ...     l10 = m["last_10"]
            ...     print(f"{m['market']}: line {m['recent_line']}, "
            ...           f"L10 {l10['over']}-{l10['under']} "
            ...           f"({l10['over_pct']}% over)")
        """
        params: dict[str, Any] = {}
        if market:
            params["market"] = market
        if dfs_odds_type:
            params["dfs_odds_type"] = dfs_odds_type

        return self._request(
            "GET",
            f"/sports/{sport}/players/{player_name}/trends",
            params=params,
        )

    def get_futures(self, sport: str) -> list[dict]:
        """
        List futures markets for a sport — championship winner, MVP,
        division winner, season win totals, etc. Each row is one (futures
        event, book, market) with every team or player priced. Free tier;
        aggregated across each book's futures feed (Bovada, FanDuel,
        DraftKings, and Pinnacle).

        Args:
            sport: Sport key (e.g. "baseball_mlb", "basketball_nba").

        Returns:
            List of futures events. Each event: id, sport_key, title,
            commence_time, markets. Each market: key (slugified
            description like "world_series_winner"), description,
            bookmaker, bookmaker_title, last_update, book_updated_at,
            outcomes. Each outcome: name, price, price_decimal.

        Example:
            >>> futures = client.get_futures("baseball_mlb")
            >>> for event in futures:
            ...     print(f"{event['title']} @ {event['commence_time']}")
            ...     for m in event["markets"]:
            ...         top3 = sorted(m["outcomes"], key=lambda o: o["price"])[:3]
            ...         for o in top3:
            ...             print(f"  {o['name']:<25} {o['price']:+}")
        """
        return self._request("GET", f"/sports/{sport}/futures")

    def get_event_ev(
        self,
        sport: str,
        event_id: int | str,
        markets: str | list[str] | None = None,
        bookmakers: str | list[str] | None = None,
    ) -> dict:
        """
        Cross-book +EV analysis for a single event.

        Groups every outcome by (market, player, line) across the books we
        carry, derives a no-vig fair line from a sharp anchor, and computes
        EV% for every other book's price at the same line. Outcomes are
        sorted with +EV plays floated to the top of each line group.

        The anchor is chosen PER LINE, in the order pinnacle -> polymarket
        -> kalshi -> bovada, and the line's ``fair_source`` always names the
        one used (``fair_source_default`` carries the order). One response
        routinely mixes several anchors, so read ``fair_source`` per line
        rather than assuming Pinnacle anchored all of them.

        PrizePicks is excluded — its synthetic +100/+100 prices aren't
        payout odds. Lines without sharp-anchor coverage on this event are
        dropped from the response.

        Pro tier required (returns 403 on free).

        Args:
            sport: Sport key (e.g. "baseball_mlb").
            event_id: Event ID (int or string).
            markets: Optional comma-separated string or list of market keys
                to evaluate (e.g. ["pitcher_strikeouts", "batter_hits"]).
                Omit to evaluate every market on the event.
            bookmakers: Optional bookmaker key(s) to restrict the returned
                prices to (e.g. ["draftkings", "fanduel"]) — shop only the
                books you hold accounts at. This narrows the PRICES, never
                the fair-line anchor: ``bookmakers="draftkings"`` still
                returns DraftKings EV% measured against Pinnacle. Lines
                where none of your books quote a price are omitted.

        Returns:
            Dict with keys: id, sport_key, home_team, away_team,
            commence_time, fair_source_default, lines.
            Each line: market_key, description, point, fair_source,
            fair_probs, outcomes. Each outcome: book, book_title, name,
            price, ev_pct, is_plus_ev.

        Example:
            >>> ev = client.get_event_ev("baseball_mlb", 12345)
            >>> for line in ev["lines"]:
            ...     plus = [o for o in line["outcomes"] if o["is_plus_ev"]]
            ...     if plus:
            ...         print(f"{line['market_key']} {line['description']} "
            ...               f"{line['point']}: {len(plus)} +EV plays")
        """
        params: dict[str, Any] = {}
        if markets:
            params["markets"] = (
                ",".join(markets) if isinstance(markets, list) else markets
            )
        if bookmakers:
            params["bookmakers"] = (
                bookmakers if isinstance(bookmakers, str) else ",".join(bookmakers)
            )
        return self._request(
            "GET",
            f"/sports/{sport}/events/{event_id}/ev",
            params=params,
        )

    def get_event_best_line(
        self,
        sport: str,
        event_id: int | str,
        markets: str | list[str] | None = None,
        bookmakers: str | list[str] | None = None,
        include_links: bool = False,
    ) -> dict:
        """
        Cross-book best-line lookup for a single event.

        For each (market, player, line) tuple, returns the single best
        American price across every comparable book we carry, with the
        book name attached. Companion to get_event_ev: best-line tells
        you which book has the highest payout right now; +EV tells you
        whether that price beats a sharp no-vig fair line. Most line
        shoppers want both.

        DFS pick'em books (PrizePicks, Sleeper, Dabble) are excluded —
        their quotes aren't independently bettable payouts; Underdog is
        included only at its clean two-way lines
        (payout_multiplier == 1.0).

        Hobby tier or higher sees prices. Free tier gets a redacted
        teaser: the full structure — every line, side, book identity,
        and the best-first ranking — with every price set to None, plus
        ``redacted: True`` and an ``upgrade_url``.

        Args:
            sport: Sport key (e.g. "baseball_mlb").
            event_id: Event ID (int or string).
            markets: Optional comma-separated string or list of market
                keys to evaluate (e.g. ["pitcher_strikeouts", "h2h"]).
                Omit to include every market on the event.
            bookmakers: Optional comma-separated string or list of book
                keys (e.g. ["draftkings", "fanduel"]) — shop only the
                books you hold accounts at. Omit for all comparable
                books.
            include_links: When True, every price row carries a ``link``
                — that book's public event-page URL, the click-out for
                "go bet this". Books without a verified URL template
                return ``None``. Links appear on free-tier redacted
                responses too (navigation isn't the paid data). Also adds
                ``app_link`` — a mobile app-open deep link (ProphetX only
                today, ``None`` elsewhere).

        Returns:
            Dict with keys: id, sport_key, home_team, away_team,
            commence_time, books_considered, lines. Each line:
            market_key, description (player name or ""), point,
            sides. `sides` is a dict mapping side name (e.g. "Over",
            "Under", or a team name) to a dict with `best` (single
            BestPrice) and `all_prices` (list of BestPrice sorted
            best-first, one row per book). Each BestPrice has `book`,
            `book_title`, `price`, `last_update` (when that book last
            refreshed the market — discount stale quotes).

        Example:
            >>> bl = client.get_event_best_line("baseball_mlb", 12345)
            >>> for line in bl["lines"]:
            ...     for side, info in line["sides"].items():
            ...         print(f"{line['description']} {side} {line['point']}: "
            ...               f"{info['best']['price']} @ {info['best']['book_title']}")
        """
        params: dict[str, Any] = {}
        if markets:
            params["markets"] = (
                ",".join(markets) if isinstance(markets, list) else markets
            )
        if bookmakers:
            params["bookmakers"] = (
                ",".join(bookmakers) if isinstance(bookmakers, list) else bookmakers
            )
        if include_links:
            params["includeLinks"] = "true"
        return self._request(
            "GET",
            f"/sports/{sport}/events/{event_id}/best-line",
            params=params,
        )

    def calc_event_ev(
        self,
        sport: str,
        event_id: int | str,
        market: str,
        name: str,
        price: int,
        point: float | None = None,
        description: str = "",
    ) -> dict:
        """
        Calculate EV% for a user-supplied price against the event's
        no-vig fair anchor. Useful for books PropLine doesn't carry —
        Caesars, BetMGM, Fanatics, BetUS, Hard Rock — where you have
        a price in hand and want to know if it's +EV against the
        sharp consensus we DO carry.

        Same fair-line math as `get_event_ev` (Pinnacle-preferred
        anchor, no-vig devigging) but takes one user price as input
        instead of returning every covered book's price as output.

        Pro tier required.

        Args:
            sport: Sport key (e.g. "baseball_mlb").
            event_id: Event ID (int or string).
            market: Market key — h2h / spreads / totals / pitcher_strikeouts / etc.
            name: Outcome name. Team name for h2h/spreads; "Over" or
                "Under" for totals and player props.
            price: American odds at your book, e.g. -118 or 145.
            point: Line/point for spreads, totals, and player props.
                Spread sign matters: -1.5 for the favorite. Omit for h2h.
            description: Player name for player-prop markets. Omit for
                game-line markets.

        Returns:
            Dict with: market, name, point, description, price,
            fair_source, fair_prob, implied_prob, ev_pct, is_plus_ev.

        Raises:
            On 404 (no fair-anchored line for the requested tuple) the
            response detail carries an `available_lines_for_market`
            list so you can correct the inputs.

        Example:
            >>> result = client.calc_event_ev(
            ...     "baseball_mlb", event_id=12614,
            ...     market="h2h", name="Pittsburgh Pirates", price=-118,
            ... )
            >>> print(f"EV {result['ev_pct']:+.2f}%  fair={result['fair_prob']}")
            EV +2.04%  fair=0.5523
        """
        params: dict[str, Any] = {
            "market": market,
            "name": name,
            "price": price,
        }
        if point is not None:
            params["point"] = point
        if description:
            params["description"] = description
        return self._request(
            "GET",
            f"/sports/{sport}/events/{event_id}/ev/calc",
            params=params,
        )

    def export_resolved_props(
        self,
        sport: str,
        market: str | None = None,
        bookmaker: str | None = None,
        since: str | None = None,
        until: str | None = None,
        out_path: str | None = None,
    ) -> str | bytes:
        """
        Download a bulk CSV export of resolved prop outcomes. Pro+ tier.

        Each row is one resolved outcome with event context, line, price,
        resolution (won/lost/push/void), and actual stat value. Use this
        for backtesting, model training, or statistical research —
        capabilities the-odds-api can't match since they don't resolve
        props.

        Args:
            sport: Sport key (e.g. "baseball_mlb"). Required.
            market: Optional market filter (e.g. "pitcher_strikeouts").
            bookmaker: Optional book filter (e.g. "draftkings").
            since: Optional ISO datetime lower bound on ``resolved_at``
                (e.g. "2026-04-01T00:00:00Z").
            until: Optional ISO datetime upper bound.
            out_path: If provided, stream the CSV to this file path and
                return the path. Otherwise return the full CSV as bytes.

        Returns:
            Path string if ``out_path`` was supplied, else the CSV content
            as bytes.

        Example (save to disk):
            >>> client.export_resolved_props(
            ...     sport="baseball_mlb",
            ...     market="pitcher_strikeouts",
            ...     since="2026-04-01T00:00:00Z",
            ...     out_path="./mlb-strikeouts.csv",
            ... )

        Example (parse in memory with pandas):
            >>> import io, pandas as pd
            >>> data = client.export_resolved_props("baseball_mlb")
            >>> df = pd.read_csv(io.BytesIO(data))
            >>> df.query("resolution == 'won'")["actual_value"].mean()
        """
        params: dict[str, Any] = {"sport": sport}
        if market:
            params["market"] = market
        if bookmaker:
            params["bookmaker"] = bookmaker
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        url = f"{self.base_url}/exports/resolved-props"
        with self._client.stream("GET", url, params=params) as resp:
            self._capture_quota(resp)
            if resp.status_code == 401:
                raise AuthError(401, "Invalid API key")
            if resp.status_code == 403:
                resp.read()
                detail = resp.json().get("detail", "Pro tier required")
                raise PropLineError(403, detail)
            if resp.status_code >= 400:
                resp.read()
                raise PropLineError(resp.status_code, resp.text)

            if out_path:
                with open(out_path, "wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
                return out_path
            return b"".join(resp.iter_bytes())

    def export_odds_history(
        self,
        sport: str,
        market: str | None = None,
        bookmaker: str | None = None,
        since: str | None = None,
        until: str | None = None,
        out_path: str | None = None,
    ) -> str | bytes:
        """
        Download the full line-movement time-series as CSV.

        One row per (outcome, snapshot): every recorded odds snapshot
        (price + line, per book, including period markets), not just the
        closing line. This is the raw tick history that no subscription
        tier can pull in bulk — Pro/Streaming get per-event
        ``get_odds_history`` only; this bulk firehose is exclusive to the
        one-time Historical Backfill pass and Enterprise.

        A full archive runs to gigabytes per sport — page month by month
        with ``since``/``until`` so each download stays manageable.

        Args:
            sport: Sport key (e.g. "baseball_mlb"). Required.
            market: Optional market filter (e.g. "pitcher_strikeouts").
            bookmaker: Optional book filter (e.g. "draftkings").
            since: Optional ISO datetime lower bound on ``recorded_at``
                (e.g. "2026-04-01T00:00:00Z").
            until: Optional ISO datetime upper bound on ``recorded_at``.
            out_path: If provided, stream the CSV to this file path and
                return the path. Otherwise return the full CSV as bytes.

        Returns:
            Path string if ``out_path`` was supplied, else the CSV content
            as bytes.

        Example (one month to disk):
            >>> client.export_odds_history(
            ...     sport="baseball_mlb",
            ...     since="2026-04-01T00:00:00Z",
            ...     until="2026-05-01T00:00:00Z",
            ...     out_path="./mlb-line-history-apr.csv",
            ... )
        """
        params: dict[str, Any] = {"sport": sport}
        if market:
            params["market"] = market
        if bookmaker:
            params["bookmaker"] = bookmaker
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        url = f"{self.base_url}/exports/odds-history"
        with self._client.stream("GET", url, params=params) as resp:
            self._capture_quota(resp)
            if resp.status_code == 401:
                raise AuthError(401, "Invalid API key")
            if resp.status_code == 403:
                resp.read()
                detail = resp.json().get(
                    "detail", "Historical Backfill pass or Enterprise required"
                )
                raise PropLineError(403, detail)
            if resp.status_code >= 400:
                resp.read()
                raise PropLineError(resp.status_code, resp.text)

            if out_path:
                with open(out_path, "wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
                return out_path
            return b"".join(resp.iter_bytes())

    def get_resolution_summary(self, days: int = 30) -> dict:
        """
        Factual volume of graded player props over the last N days.

        Aggregated counts only — a coverage proof (every outcome counted
        was graded against the real box score), never a profitability
        claim. Free tier.

        Args:
            days: Look-back window, 1-90 (default: 30)

        Returns:
            Dict with: days, total_graded (incl. void), total_settled
            (won/lost/push), events_graded, sports_covered, by_sport
            (list of {sport_key, title, graded, events}), and top_markets
            (top 12 {market_key, graded}).

        Example:
            >>> s = client.get_resolution_summary(days=30)
            >>> print(f"{s['total_graded']:,} props graded across "
            ...       f"{s['sports_covered']} sports")
        """
        return self._request(
            "GET", "/markets/resolution-summary", params={"days": days}
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
        min_steam_score: float | None = None,
        min_books_agreeing: int | None = None,
        batch_max: int | None = None,
    ) -> dict:
        """
        Register a webhook subscription. Streaming tier only.

        The returned dict includes the full signing ``secret`` — this is the
        ONLY time the secret is returned. Subsequent calls return a masked
        value. Store it securely.

        Args:
            url: HTTPS URL that will receive POSTed events.
            events: Event types to subscribe to. Default: all.
                Valid values: "line_movement", "resolution", "steam",
                "market_suspended".
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
            min_steam_score: Minimum 0-100 steam score to trigger a
                ``steam`` event (cross-book sharp-money move). Filters weak
                moves; null uses the detector's global floor.
            min_books_agreeing: ``market_suspended`` only — how many books
                must have pulled the same player/market on the same event
                before you are told. Unset/1 = every drop (right if you
                price off one book and need to know the instant its
                number vanishes); 3+ = corroborated late scratches only.
                Every payload carries ``books_agreeing`` regardless.
            batch_max: Batched delivery opt-in (1-500). Up to N events
                arrive per POST as a signed envelope ``{"batch": true,
                "event_type": ..., "count": N, "events": [{"delivery_id":
                ..., "data": <per-event payload>}, ...]}`` with an
                ``X-PropLine-Batch`` header. Strongly recommended for
                high-volume subscriptions (sport-wide line_movement can
                exceed 1,000 events/min) — one POST per event caps your
                delivery rate at your endpoint's response time. ``0``
                reverts to per-event. JSON format only.

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
        if min_steam_score is not None:
            body["min_steam_score"] = min_steam_score
        if min_books_agreeing is not None:
            body["min_books_agreeing"] = min_books_agreeing
        if batch_max is not None:
            body["batch_max"] = batch_max
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
        min_steam_score: float | None = None,
        min_books_agreeing: int | None = None,
        batch_max: int | None = None,
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
        if min_steam_score is not None:
            body["min_steam_score"] = min_steam_score
        if min_books_agreeing is not None:
            body["min_books_agreeing"] = min_books_agreeing
        if batch_max is not None:
            body["batch_max"] = batch_max
        if active is not None:
            body["active"] = active
        return self._request("PATCH", f"/webhooks/{webhook_id}", json=body)

    def delete_webhook(self, webhook_id: int) -> dict:
        """Delete a webhook and cascade-remove its delivery history."""
        return self._request("DELETE", f"/webhooks/{webhook_id}")

    def test_webhook(self, webhook_id: int) -> dict:
        """Queue a sample ``test`` payload to the webhook's URL."""
        return self._request("POST", f"/webhooks/{webhook_id}/test")

    def list_webhook_deliveries(
        self,
        webhook_id: int,
        limit: int = 50,
        before_id: int | None = None,
    ) -> list[dict]:
        """
        Return recent delivery attempts for a webhook, newest first.

        Each delivery has ``status`` (pending/success/failed), ``response_code``,
        ``attempts``, ``delivered_at``, and the ``payload`` that was sent.

        ``before_id`` pages backwards: pass the smallest ``id`` from the
        previous page to get the next-older page. A page shorter than
        ``limit`` (max 200) is the last one.
        """
        params: dict = {"limit": limit}
        if before_id is not None:
            params["before_id"] = before_id
        return self._request(
            "GET",
            f"/webhooks/{webhook_id}/deliveries",
            params=params,
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

    def grade_clv(self, bets: list[dict]) -> dict:
        """
        Grade placed bets against their closing lines (CLV).

        Closing line value is the only durable proxy for whether a
        bettor has edge: did the price you took beat the number the
        market settled on? Send the bets you actually placed and each
        comes back with its closing price, the de-vigged closing fair
        probability, CLV, and — once the game settles — the graded
        result and actual stat value.

        Stateless: nothing is stored server-side.

        Hobby+ required. Free tier receives the full structure and
        match verdicts with every number nulled.

        Args:
            bets: Up to 500 bet dicts. Required keys per bet:
                sport_key, event_id, market, bookmaker, selection,
                price. Optional: ref (echoed back so you can align
                rows without relying on order), side ("Over"/"Under";
                omit for YES-only props), point, period, stake
                (defaults to 1 unit for profit_units).

        Returns:
            Dict with `summary` and `bets`. Each graded bet carries
            closing_price, closing_point, closing_at, closing_is_stale,
            closing_is_final, fair_source, closing_fair_prob, clv_pct,
            ev_vs_close_pct, beat_close, resolution, actual_value.

        Note:
            TWO CLV numbers are returned deliberately. `clv_pct` is
            price-vs-price — familiar and quotable, but vig-blind, so
            it flatters a bet taken on the juicy side of a wide market.
            `ev_vs_close_pct` scores your price against the DE-VIGGED
            close and is the honest one. They can disagree by several
            points on the same bet.

            The de-vig uses the sharpest book quoting that line at
            close (reported as `fair_source`), not the book you bet
            at — de-vigging your own book always returns a negative
            number, because you paid its hold.

            Bets whose event has not started carry
            `closing_is_final: False`, are counted in
            `summary["pending"]`, and are excluded from the summary
            averages: before kickoff the "closing" price is just the
            latest price, so its CLV is ~0 by construction.

            Matching is fail-closed. A bet that cannot be pinned to
            exactly one stored outcome returns `matched: False` with an
            `unmatched_reason` rather than a confident wrong match.

        Example:
            >>> res = client.grade_clv([{
            ...     "ref": "b1",
            ...     "sport_key": "baseball_mlb",
            ...     "event_id": 150791,
            ...     "market": "batter_hits_runs_rbis",
            ...     "bookmaker": "lowvig",
            ...     "selection": "Drake Baldwin",
            ...     "side": "Under",
            ...     "point": 0.5,
            ...     "price": 145,
            ...     "stake": 1,
            ... }])
            >>> print(res["summary"]["avg_ev_vs_close_pct"])
            0.08
        """
        return self._request("POST", "/clv/grade", json=bets)

    # ------------------------------------------------------------------

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
