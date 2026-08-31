"""PropLine — Python SDK for the PropLine player props API."""

from propline.client import (
    AuthError,
    PropLine,
    PropLineError,
    QuotaStatus,
    RateLimitError,
)


class Bookmaker:
    """String constants for bookmaker keys in odds responses."""

    BOVADA = "bovada"
    DRAFTKINGS = "draftkings"
    FANDUEL = "fanduel"
    PINNACLE = "pinnacle"
    UNIBET = "unibet"
    UNDERDOG = "underdog"
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"
    PRIZEPICKS = "prizepicks"


__version__ = "0.49.0"
__all__ = [
    "PropLine",
    "Bookmaker",
    "QuotaStatus",
    "PropLineError",
    "RateLimitError",
    "AuthError",
]
