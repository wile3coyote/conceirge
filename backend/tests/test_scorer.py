"""Unit tests for backend/services/scorer.py — pure logic, no I/O."""

import pytest

from backend.config import Settings
from backend.exceptions import ScoringError
from backend.models.release import ScoredRelease
from backend.services.scorer import detect_quality, score_release, score_releases

# ---------------------------------------------------------------------------
# Shared test settings — no DB, no async
# ---------------------------------------------------------------------------

SETTINGS = Settings(
    radarr_url="http://localhost:7878",
    max_size_gb=40.0,
    avoid_keywords=["CAM", "HDCAM"],
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def make_release(
    title: str = "Movie.2160p.BluRay",
    size: int = 10 * 1024**3,
    resolution: int = 2160,
    guid: str = "guid-1",
) -> dict:
    return {
        "guid": guid,
        "title": title,
        "size": size,
        "quality": {"quality": {"name": "Bluray-2160p", "resolution": resolution}},
    }


# ---------------------------------------------------------------------------
# detect_quality
# ---------------------------------------------------------------------------


class TestDetectQuality:
    def test_2160p_via_resolution(self):
        assert detect_quality("Some.Movie", 2160) == "2160p"

    def test_2160p_via_title_4k_keyword(self):
        assert detect_quality("Movie.4K.BluRay", 0) == "2160p"

    def test_2160p_via_title_uhd_keyword(self):
        assert detect_quality("Movie.UHD.BluRay", 0) == "2160p"

    def test_1080p_via_resolution(self):
        assert detect_quality("Some.Movie", 1080) == "1080p"

    def test_1080p_via_title_keyword(self):
        assert detect_quality("Movie.1080p.BluRay", 0) == "1080p"

    def test_720p_via_resolution(self):
        assert detect_quality("Some.Movie", 720) == "720p"

    def test_unknown_when_no_match(self):
        assert detect_quality("Some.Movie.DVDRip", 0) == "unknown"

    def test_resolution_takes_priority_over_title(self):
        # resolution=2160 wins even when the title says 720p
        assert detect_quality("Movie.720p.BluRay", 2160) == "2160p"


# ---------------------------------------------------------------------------
# score_release
# ---------------------------------------------------------------------------


class TestScoreRelease:
    def test_2160p_not_rejected(self):
        release = make_release(title="Movie.2160p.BluRay", resolution=2160)
        result = score_release(release, SETTINGS)

        assert result.rejected is False
        assert result.score == 100
        assert result.quality == "2160p"

    def test_1080p_not_rejected(self):
        release = make_release(
            title="Movie.1080p.BluRay", resolution=1080, size=8 * 1024**3
        )
        result = score_release(release, SETTINGS)

        assert result.rejected is False
        assert result.score == 50
        assert result.quality == "1080p"

    def test_1080p_score_lower_than_2160p(self):
        r_2160 = score_release(
            make_release(title="Movie.2160p.BluRay", resolution=2160), SETTINGS
        )
        r_1080 = score_release(
            make_release(
                title="Movie.1080p.BluRay", resolution=1080, guid="guid-2"
            ),
            SETTINGS,
        )
        assert r_2160.score > r_1080.score

    def test_720p_rejected_with_reason(self):
        release = make_release(
            title="Movie.720p.BluRay", resolution=720, size=4 * 1024**3
        )
        result = score_release(release, SETTINGS)

        assert result.rejected is True
        assert result.reject_reason is not None
        assert "quality not accepted" in result.reject_reason

    def test_size_within_tolerance_not_rejected(self):
        # 44 GB is within 20% of 40 GB limit (hard limit = 48 GB) — accepted
        release = make_release(
            title="Movie.2160p.BluRay",
            resolution=2160,
            size=44 * 1024**3,
        )
        result = score_release(release, SETTINGS)

        assert result.rejected is False

    def test_size_over_tolerance_rejected(self):
        # 50 GB exceeds the 48 GB hard limit (40 GB + 20%) — rejected
        release = make_release(
            title="Movie.2160p.BluRay",
            resolution=2160,
            size=50 * 1024**3,
        )
        result = score_release(release, SETTINGS)

        assert result.rejected is True
        assert result.reject_reason is not None
        assert "too large" in result.reject_reason

    def test_size_exactly_at_limit_not_rejected(self):
        # 40 GB exactly should not be rejected
        release = make_release(
            title="Movie.2160p.BluRay",
            resolution=2160,
            size=int(40 * 1024**3),
        )
        result = score_release(release, SETTINGS)

        assert result.rejected is False

    def test_blocked_keyword_cam_rejected(self):
        release = make_release(
            title="Movie.2160p.CAM.x264", resolution=2160
        )
        result = score_release(release, SETTINGS)

        assert result.rejected is True
        assert result.reject_reason is not None
        assert "blocked keyword" in result.reject_reason

    def test_blocked_keyword_case_insensitive(self):
        # "cam" lowercase in title should match "CAM" in avoid_keywords
        release = make_release(
            title="Movie.2160p.cam.x264", resolution=2160
        )
        result = score_release(release, SETTINGS)

        assert result.rejected is True
        assert result.reject_reason is not None
        assert "blocked keyword" in result.reject_reason

    def test_blocked_keyword_hdcam_rejected(self):
        release = make_release(
            title="Movie.2160p.HDCAM.x264", resolution=2160
        )
        result = score_release(release, SETTINGS)

        assert result.rejected is True
        assert result.reject_reason is not None
        assert "blocked keyword" in result.reject_reason

    def test_size_gb_calculated_correctly(self):
        size_bytes = 15 * 1024**3
        release = make_release(
            title="Movie.2160p.BluRay", resolution=2160, size=size_bytes
        )
        result = score_release(release, SETTINGS)

        assert result.size_gb == pytest.approx(size_bytes / 1024**3)

    def test_missing_guid_raises_scoring_error(self):
        release = {"title": "Movie.2160p.BluRay", "size": 10 * 1024**3}
        with pytest.raises(ScoringError):
            score_release(release, SETTINGS)

    def test_missing_title_raises_scoring_error(self):
        release = {"guid": "guid-1", "size": 10 * 1024**3}
        with pytest.raises(ScoringError):
            score_release(release, SETTINGS)

    def test_reject_reason_none_for_valid_release(self):
        release = make_release(title="Movie.2160p.BluRay", resolution=2160)
        result = score_release(release, SETTINGS)

        assert result.reject_reason is None

    def test_radarr_guid_preserved(self):
        release = make_release(guid="my-unique-guid")
        result = score_release(release, SETTINGS)

        assert result.radarr_guid == "my-unique-guid"


# ---------------------------------------------------------------------------
# Parametrized detection + scoring coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title, resolution, expected_quality",
    [
        ("Movie.2160p.WEB-DL", 2160, "2160p"),
        ("Movie.4K.WEB-DL", 0, "2160p"),
        ("Movie.UHD.WEB-DL", 0, "2160p"),
        ("Movie.1080p.WEB-DL", 1080, "1080p"),
        ("Movie.1080p.BluRay", 0, "1080p"),
        ("Movie.720p.WEB-DL", 720, "720p"),
        ("Movie.DVDRip", 0, "unknown"),
    ],
)
def test_detect_quality_parametrized(title, resolution, expected_quality):
    assert detect_quality(title, resolution) == expected_quality


@pytest.mark.parametrize(
    "title, resolution, size_gb, expected_rejected, reason_fragment",
    [
        ("Movie.2160p.WEB-DL", 2160, 28, False, None),
        ("Movie.1080p.WEB-DL", 1080, 15, False, None),
        ("Movie.720p.BluRay", 720, 4, True, "quality not accepted"),
        ("Movie.2160p.CAM.x264", 2160, 10, True, "blocked keyword"),
        ("Movie.HDCAM.2160p", 2160, 10, True, "blocked keyword"),
        ("Movie.2160p.BluRay", 2160, 50, True, "too large"),
    ],
)
def test_score_release_parametrized(
    title, resolution, size_gb, expected_rejected, reason_fragment
):
    release = make_release(title=title, resolution=resolution, size=int(size_gb * 1024**3))
    result = score_release(release, SETTINGS)

    assert result.rejected is expected_rejected
    if reason_fragment is not None:
        assert reason_fragment in result.reject_reason
    else:
        assert result.reject_reason is None


# ---------------------------------------------------------------------------
# score_releases
# ---------------------------------------------------------------------------


class TestScoreReleases:
    def test_empty_list_returns_empty(self):
        assert score_releases([], SETTINGS) == []

    def test_single_valid_release(self):
        releases = [make_release(title="Movie.2160p.BluRay", resolution=2160)]
        result = score_releases(releases, SETTINGS)

        assert len(result) == 1
        assert result[0].rejected is False

    def test_non_rejected_sorted_by_score_descending(self):
        releases = [
            make_release(
                title="Movie.1080p.BluRay",
                resolution=1080,
                size=8 * 1024**3,
                guid="guid-1080",
            ),
            make_release(
                title="Movie.2160p.BluRay",
                resolution=2160,
                size=15 * 1024**3,
                guid="guid-2160",
            ),
        ]
        result = score_releases(releases, SETTINGS)

        assert result[0].radarr_guid == "guid-2160"
        assert result[1].radarr_guid == "guid-1080"
        assert result[0].score >= result[1].score

    def test_rejected_releases_at_end(self):
        releases = [
            make_release(
                title="Movie.2160p.CAM.x264",
                resolution=2160,
                guid="guid-cam",
            ),
            make_release(
                title="Movie.2160p.BluRay",
                resolution=2160,
                guid="guid-good",
            ),
        ]
        result = score_releases(releases, SETTINGS)

        assert result[0].radarr_guid == "guid-good"
        assert result[0].rejected is False
        assert result[1].radarr_guid == "guid-cam"
        assert result[1].rejected is True

    def test_mixed_valid_and_rejected_ordering(self):
        releases = [
            make_release(
                title="Movie.2160p.BluRay",
                resolution=2160,
                guid="r-2160",
            ),
            make_release(
                title="Movie.1080p.BluRay",
                resolution=1080,
                size=8 * 1024**3,
                guid="r-1080",
            ),
            make_release(
                title="Movie.720p.BluRay",
                resolution=720,
                size=2 * 1024**3,
                guid="r-720",
            ),
        ]
        result = score_releases(releases, SETTINGS)

        guids = [r.radarr_guid for r in result]
        assert guids.index("r-2160") < guids.index("r-1080")
        assert guids.index("r-1080") < guids.index("r-720")
        assert result[-1].rejected is True

    def test_all_rejected_returns_all_at_end(self):
        releases = [
            make_release(title="Movie.720p.BluRay", resolution=720, guid="r1"),
            make_release(title="Movie.720p.WEB", resolution=720, guid="r2"),
        ]
        result = score_releases(releases, SETTINGS)

        assert len(result) == 2
        assert all(r.rejected for r in result)

    def test_returns_scored_release_instances(self):
        releases = [make_release()]
        result = score_releases(releases, SETTINGS)

        assert all(isinstance(r, ScoredRelease) for r in result)

    def test_malformed_release_raises_scoring_error(self):
        # A release missing 'title' should propagate ScoringError out of score_releases
        releases = [{"guid": "g1"}]
        with pytest.raises(ScoringError):
            score_releases(releases, SETTINGS)
