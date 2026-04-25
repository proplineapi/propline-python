"""PropLine — Python SDK for the PropLine player props API."""

from propline.client import PropLine


class Bookmaker:
    """String constants for bookmaker keys in odds responses."""

    BOVADA = "bovada"
    DRAFTKINGS = "draftkings"
    FANDUEL = "fanduel"
    PINNACLE = "pinnacle"
    PRIZEPICKS = "prizepicks"
    UNIBET = "unibet"


__version__ = "0.8.0"
__all__ = ["PropLine", "Bookmaker"]
