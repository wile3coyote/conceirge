from backend.config import Settings
from backend.exceptions import ScoringError
from backend.models.release import ScoredRelease

_QUALITY_SCORES: dict[str, int] = {
    "2160p": 100,
    "1080p": 50,
}

_REJECTED_QUALITIES: frozenset[str] = frozenset({"720p", "unknown"})


def detect_quality(title: str, resolution: int) -> str:
    """Infer a normalised quality label from resolution and title text.

    Priority order: 2160p → 1080p → 720p → unknown.
    Resolution field takes precedence; title keywords are checked as fallback
    within each tier.

    Args:
        title: Release title string (e.g. "Inception.2010.2160p.BluRay.x265").
        resolution: Integer resolution value from the Radarr quality block.

    Returns:
        One of ``"2160p"``, ``"1080p"``, ``"720p"``, or ``"unknown"``.
    """
    title_upper = title.upper()

    if resolution == 2160 or any(kw in title_upper for kw in ("2160P", "4K", "UHD")):
        return "2160p"
    if resolution == 1080 or "1080P" in title_upper:
        return "1080p"
    if resolution == 720 or "720P" in title_upper:
        return "720p"
    return "unknown"


def score_release(release: dict, settings: Settings) -> ScoredRelease:
    """Score a single Radarr release dict against the current settings.

    Applies rejection rules in order: blocklist keywords → size cap → quality
    filter. The first matching rule short-circuits; non-rejected releases
    receive a quality-based numeric score.

    Args:
        release: Raw release dict from Radarr (see module docstring for shape).
        settings: Application settings providing scoring thresholds and lists.

    Returns:
        A ``ScoredRelease`` instance with score and optional rejection reason.

    Raises:
        ScoringError: If the release dict is missing the required ``"title"``
            or ``"guid"`` keys, indicating malformed upstream data.
    """
    title: str | None = release.get("title")
    guid: str | None = release.get("guid")

    if not isinstance(title, str):
        raise ScoringError(
            f"release missing required 'title' field: {release!r}",
            code="scoring_error",
        )
    if not isinstance(guid, str):
        raise ScoringError(
            f"release missing required 'guid' field: {release!r}",
            code="scoring_error",
        )

    size: int = release.get("size", 0) or 0
    indexer_id: int = release.get("indexerId", 0) or 0

    quality_block: dict = (
        release.get("quality", {}) or {}
    ).get("quality", {}) or {}

    resolution: int = quality_block.get("resolution", 0) or 0

    quality = detect_quality(title, resolution)

    # --- Rejection rule 1: blocklist keywords ---
    title_lower = title.lower()
    for keyword in settings.avoid_keywords:
        if keyword.lower() in title_lower:
            return ScoredRelease(
                radarr_guid=guid,
                title=title,
                size_gb=size / 1024**3,
                quality=quality,
                score=0,
                rejected=True,
                reject_reason=f"blocked keyword: {keyword}",
                indexer_id=indexer_id,
            )

    # --- Rejection rule 2: size cap (with tolerance band) ---
    size_gb = size / 1024**3
    hard_limit_gb = settings.max_size_gb * (1 + settings.max_size_tolerance_pct / 100)
    if size_gb > hard_limit_gb:
        return ScoredRelease(
            radarr_guid=guid,
            title=title,
            size_gb=size_gb,
            quality=quality,
            score=0,
            rejected=True,
            reject_reason=f"too large: {size_gb:.1f} GB",
            indexer_id=indexer_id,
        )

    # --- Rejection rule 3: quality filter ---
    if quality in _REJECTED_QUALITIES:
        return ScoredRelease(
            radarr_guid=guid,
            title=title,
            size_gb=size_gb,
            quality=quality,
            score=0,
            rejected=True,
            reject_reason=f"quality not accepted: {quality}",
            indexer_id=indexer_id,
        )

    return ScoredRelease(
        radarr_guid=guid,
        title=title,
        size_gb=size_gb,
        quality=quality,
        score=_QUALITY_SCORES.get(quality, 0),
        rejected=False,
        reject_reason=None,
        indexer_id=indexer_id,
    )


def score_releases(releases: list[dict], settings: Settings) -> list[ScoredRelease]:
    """Score and sort a list of Radarr release dicts.

    Non-rejected releases are sorted by score descending; rejected releases
    follow in their original order.

    Args:
        releases: List of raw Radarr release dicts.
        settings: Application settings.

    Returns:
        Sorted list of ``ScoredRelease`` instances, empty list if input is empty.
    """
    if not releases:
        return []

    scored = [score_release(r, settings) for r in releases]

    accepted = sorted(
        (r for r in scored if not r.rejected),
        key=lambda r: r.score,
        reverse=True,
    )
    rejected = [r for r in scored if r.rejected]

    return accepted + rejected
