"""Tests for src/analysis/pitcher_fatigue.py."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.analysis.pitcher_fatigue import (
    FatigueBucket,
    _aggregate_into_buckets,
    _detect_fatigue_threshold,
    compute_pitcher_fatigue,
)


def _make_row(pitch_number: int, result: str):
    """Create a minimal mock row object for pitcher pitch events."""
    class _Row:
        pitch_number_game = pitch_number
        pa_result = result
    return _Row()


def _make_bucket(
    idx: int,
    bf: int,
    hits: int,
    walks: int,
    ks: int,
    bucket_size: int = 15,
) -> FatigueBucket:
    ab = bf - walks
    return FatigueBucket(
        bucket_index=idx,
        pitch_start=idx * bucket_size + 1,
        pitch_end=(idx + 1) * bucket_size,
        batters_faced=bf,
        hits=hits,
        walks=walks,
        strikeouts=ks,
        ba_against=round(hits / ab, 3) if ab > 0 else None,
        k_pct=round(ks / bf, 3) if bf > 0 else None,
        bb_pct=round(walks / bf, 3) if bf > 0 else None,
        is_fatigue_point=False,
    )


# ─────────────────────────────────────────────────────────────────
# _assign_bucket (pitch_number → bucket label)
# ─────────────────────────────────────────────────────────────────

def _assign_bucket(pitch_number: int, bucket_size: int = 15) -> str:
    """Derive the bucket label string for a given pitch number."""
    idx = (pitch_number - 1) // bucket_size
    start = idx * bucket_size + 1
    end = (idx + 1) * bucket_size
    return f"{start}-{end}"


class TestAssignBucket:
    def test_first_pitch_in_first_bucket(self) -> None:
        assert _assign_bucket(1, 15) == "1-15"

    def test_last_pitch_in_first_bucket(self) -> None:
        assert _assign_bucket(15, 15) == "1-15"

    def test_first_pitch_in_second_bucket(self) -> None:
        assert _assign_bucket(16, 15) == "16-30"

    def test_bucket_31_to_45(self) -> None:
        assert _assign_bucket(31, 15) == "31-45"

    def test_bucket_size_10(self) -> None:
        assert _assign_bucket(11, 10) == "11-20"


# ─────────────────────────────────────────────────────────────────
# _detect_fatigue_threshold
# ─────────────────────────────────────────────────────────────────

class TestDetectFatigueThreshold:
    def test_returns_none_with_no_baseline(self) -> None:
        buckets = [_make_bucket(0, 5, 1, 0, 1)]
        result = _detect_fatigue_threshold(buckets, None, None)
        assert result is None

    def test_detects_ba_rise(self) -> None:
        """BA jump > 20% over baseline should trigger."""
        # baseline BA = 0.2; bucket BA = 0.3 (50% rise)
        buckets = [_make_bucket(0, 10, 2, 0, 2), _make_bucket(1, 10, 6, 0, 1)]
        # bucket 1: ba_against = 0.6, overall_ba = 0.2 → 200% rise → threshold = bucket 1 start
        result = _detect_fatigue_threshold(buckets, overall_ba=0.2, overall_k=0.2)
        assert result == buckets[1].pitch_start

    def test_detects_k_drop(self) -> None:
        """K% drop > 20% below baseline should trigger."""
        # overall_k = 0.3; bucket k_pct = 0.1 → drop of 66%
        buckets = [_make_bucket(0, 10, 2, 0, 3), _make_bucket(1, 10, 2, 0, 1)]
        result = _detect_fatigue_threshold(buckets, overall_ba=0.2, overall_k=0.3)
        assert result is not None

    def test_skips_small_bf_buckets(self) -> None:
        """Buckets with fewer than 3 batters faced should be skipped."""
        small = FatigueBucket(
            bucket_index=0, pitch_start=1, pitch_end=15,
            batters_faced=2, hits=2, walks=0, strikeouts=0,
            ba_against=1.0, k_pct=0.0, bb_pct=0.0, is_fatigue_point=False,
        )
        result = _detect_fatigue_threshold([small], overall_ba=0.2, overall_k=0.3)
        assert result is None

    def test_no_fatigue_returns_none(self) -> None:
        """Consistently good buckets should return None."""
        buckets = [_make_bucket(0, 10, 2, 0, 3), _make_bucket(1, 10, 2, 0, 3)]
        result = _detect_fatigue_threshold(buckets, overall_ba=0.2, overall_k=0.3)
        assert result is None


# ─────────────────────────────────────────────────────────────────
# _aggregate_into_buckets
# ─────────────────────────────────────────────────────────────────

class TestAggregateIntoBuckets:
    def test_basic_aggregation(self) -> None:
        rows = [_make_row(1, "single"), _make_row(2, "strikeout"), _make_row(3, "walk")]
        buckets = _aggregate_into_buckets(rows, bucket_size=15)
        assert len(buckets) == 1
        assert buckets[0].hits == 1
        assert buckets[0].strikeouts == 1
        assert buckets[0].walks == 1

    def test_two_buckets(self) -> None:
        rows = [_make_row(1, "single"), _make_row(16, "strikeout")]
        buckets = _aggregate_into_buckets(rows, bucket_size=15)
        assert len(buckets) == 2

    def test_zero_pitch_number_ignored(self) -> None:
        rows = [_make_row(0, "single"), _make_row(1, "walk")]
        buckets = _aggregate_into_buckets(rows, bucket_size=15)
        assert buckets[0].hits == 0
        assert buckets[0].walks == 1


# ─────────────────────────────────────────────────────────────────
# compute_pitcher_fatigue — integration tests
# ─────────────────────────────────────────────────────────────────

class TestComputePitcherFatigue:
    def test_returns_result_for_seeded_pitcher(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_pitcher_fatigue(db_session, "cpbl_pitcher_1", year=2026)
        assert result is not None

    def test_returns_none_for_unknown_pitcher(
        self, db_session: Session, seed_data: Session
    ) -> None:
        result = compute_pitcher_fatigue(db_session, "cpbl_nobody", year=2026)
        assert result is None

    def test_buckets_non_empty(self, db_session: Session, seed_data: Session) -> None:
        result = compute_pitcher_fatigue(db_session, "cpbl_pitcher_1", year=2026)
        assert result is not None
        assert len(result.buckets) > 0

    def test_pitcher_id_preserved(self, db_session: Session, seed_data: Session) -> None:
        result = compute_pitcher_fatigue(db_session, "cpbl_pitcher_1", year=2026)
        assert result is not None
        assert result.pitcher_id == "cpbl_pitcher_1"

    def test_year_field(self, db_session: Session, seed_data: Session) -> None:
        result = compute_pitcher_fatigue(db_session, "cpbl_pitcher_1", year=2026)
        assert result is not None
        assert result.year == 2026

    def test_total_pitches_positive(self, db_session: Session, seed_data: Session) -> None:
        result = compute_pitcher_fatigue(db_session, "cpbl_pitcher_1", year=2026)
        assert result is not None
        assert result.total_pitches > 0

    def test_wrong_year_returns_none(self, db_session: Session, seed_data: Session) -> None:
        result = compute_pitcher_fatigue(db_session, "cpbl_pitcher_1", year=1999)
        assert result is None

    def test_sample_note_is_string(self, db_session: Session, seed_data: Session) -> None:
        result = compute_pitcher_fatigue(db_session, "cpbl_pitcher_1", year=2026)
        assert result is not None
        assert isinstance(result.sample_note, str)
