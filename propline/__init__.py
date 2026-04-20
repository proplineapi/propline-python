"""PropLine — Python SDK for the PropLine player props API."""

from propline.client import PropLine


class Bookmaker:
    """String constants for bookmaker keys in odds responses."""

    BOVADA = "bovada"
    DRAFTKINGS = "draftkings"
    FANDUEL = "fanduel"
    PINNACLE = "pinnacle"


__version__ = "0.4.2"
__all__ = ["PropLine", "Bookmaker"]
