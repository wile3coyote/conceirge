class ConciergeError(Exception):
    """Base exception for all Concierge domain errors."""
    code: str = "concierge_error"

    def __init__(self, detail: str, code: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class RadarrError(ConciergeError):
    code = "radarr_error"


class JellyfinError(ConciergeError):
    code = "jellyfin_error"


class ScoringError(ConciergeError):
    code = "scoring_error"
