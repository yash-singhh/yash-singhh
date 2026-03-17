"""Unit tests for social_analyzer.analysis (trend scoring & metrics)."""

import pytest
from datetime import datetime, timedelta, timezone

from social_analyzer.analysis import (
    AnalysisConfig,
    analyse,
    _engagement_score,
    _engagement_rate,
    _ctr,
    _apply_window,
    _compute_platform_metrics,
    _rank_trends,
)
from social_analyzer.ingestion import PostRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    post_id: str = "P001",
    platform: str = "twitter",
    days_ago: int = 1,
    text: str = "Hello #ai #python world content",
    likes: float = 100.0,
    comments: float = 20.0,
    shares: float = 10.0,
    impressions: float = 2000.0,
    clicks: float = 40.0,
    followers: float = 5000.0,
) -> PostRecord:
    ts = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    return PostRecord(
        post_id=post_id,
        platform=platform,
        timestamp=ts,
        text=text,
        likes=likes,
        comments=comments,
        shares=shares,
        impressions=impressions,
        clicks=clicks,
        followers=followers,
    )


# ---------------------------------------------------------------------------
# Engagement score
# ---------------------------------------------------------------------------


class TestEngagementScore:
    def test_default_weights(self):
        cfg = AnalysisConfig()
        r = _make_record(likes=100, comments=50, shares=20)
        score = _engagement_score(r, cfg)
        # 100*1 + 50*2 + 20*3 = 260
        assert score == pytest.approx(260.0)

    def test_custom_weights(self):
        cfg = AnalysisConfig(
            engagement_weight_likes=2.0,
            engagement_weight_comments=1.0,
            engagement_weight_shares=1.0,
        )
        r = _make_record(likes=10, comments=10, shares=10)
        # 10*2 + 10*1 + 10*1 = 40
        assert _engagement_score(r, cfg) == pytest.approx(40.0)

    def test_zero_engagement(self):
        cfg = AnalysisConfig()
        r = _make_record(likes=0, comments=0, shares=0)
        assert _engagement_score(r, cfg) == 0.0


# ---------------------------------------------------------------------------
# Engagement rate
# ---------------------------------------------------------------------------


class TestEngagementRate:
    def test_with_impressions(self):
        r = _make_record(likes=100, comments=0, shares=0, impressions=1000)
        assert _engagement_rate(r) == pytest.approx(10.0)

    def test_fallback_to_followers(self):
        r = _make_record(likes=50, comments=0, shares=0, impressions=0, followers=1000)
        assert _engagement_rate(r) == pytest.approx(5.0)

    def test_zero_impressions_and_followers(self):
        r = _make_record(likes=50, impressions=0, followers=0)
        assert _engagement_rate(r) == 0.0

    def test_full_formula(self):
        # (likes + comments + shares) / impressions * 100
        r = _make_record(likes=10, comments=5, shares=5, impressions=500)
        assert _engagement_rate(r) == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# CTR
# ---------------------------------------------------------------------------


class TestCTR:
    def test_basic(self):
        r = _make_record(clicks=50, impressions=2500)
        assert _ctr(r) == pytest.approx(2.0)

    def test_zero_impressions(self):
        r = _make_record(clicks=50, impressions=0)
        assert _ctr(r) == 0.0


# ---------------------------------------------------------------------------
# Window filtering
# ---------------------------------------------------------------------------


class TestApplyWindow:
    def test_filters_old_records(self):
        records = [
            _make_record("P1", days_ago=5),
            _make_record("P2", days_ago=15),
            _make_record("P3", days_ago=35),  # outside 30-day window
        ]
        result = _apply_window(records, window_days=30)
        ids = [r.post_id for r in result]
        assert "P1" in ids
        assert "P2" in ids
        assert "P3" not in ids

    def test_zero_window_returns_all(self):
        records = [_make_record("P1", days_ago=365)]
        assert len(_apply_window(records, window_days=0)) == 1

    def test_empty_list(self):
        assert _apply_window([], window_days=30) == []


# ---------------------------------------------------------------------------
# Platform metrics
# ---------------------------------------------------------------------------


class TestComputePlatformMetrics:
    def test_groups_by_platform(self):
        records = [
            _make_record("P1", platform="twitter"),
            _make_record("P2", platform="instagram"),
            _make_record("P3", platform="twitter"),
        ]
        cfg = AnalysisConfig()
        metrics = _compute_platform_metrics(records, cfg)
        assert "twitter" in metrics
        assert "instagram" in metrics
        assert metrics["twitter"].post_count == 2
        assert metrics["instagram"].post_count == 1

    def test_aggregates_likes(self):
        records = [
            _make_record("P1", platform="twitter", likes=100),
            _make_record("P2", platform="twitter", likes=200),
        ]
        cfg = AnalysisConfig()
        metrics = _compute_platform_metrics(records, cfg)
        assert metrics["twitter"].total_likes == 300.0

    def test_avg_engagement_rate_not_negative(self):
        records = [_make_record("P1", platform="fb", impressions=0, followers=0)]
        cfg = AnalysisConfig()
        metrics = _compute_platform_metrics(records, cfg)
        assert metrics["fb"].avg_engagement_rate >= 0.0


# ---------------------------------------------------------------------------
# Trend ranking
# ---------------------------------------------------------------------------


class TestRankTrends:
    def _make_scored_records(self):
        """Return records, scores dict, and er dict for trend ranking tests."""
        r1 = _make_record("P1", text="#ai content is great", likes=500)
        r2 = _make_record("P2", text="love #ai and #python stuff", likes=300)
        r3 = _make_record("P3", text="#python is cool programming stuff", likes=200)
        records = [r1, r2, r3]
        cfg = AnalysisConfig()
        scores = {r.post_id: _engagement_score(r, cfg) for r in records}
        er = {r.post_id: _engagement_rate(r) for r in records}
        return records, scores, er, cfg

    def test_returns_trend_items(self):
        records, scores, er, cfg = self._make_scored_records()
        cfg.min_post_count = 1
        trends = _rank_trends(records, scores, er, "hashtag", cfg)
        assert len(trends) > 0

    def test_sorted_by_engagement(self):
        records, scores, er, cfg = self._make_scored_records()
        cfg.min_post_count = 1
        trends = _rank_trends(records, scores, er, "hashtag", cfg)
        engagements = [t.total_engagement for t in trends]
        assert engagements == sorted(engagements, reverse=True)

    def test_min_post_count_filter(self):
        records, scores, er, cfg = self._make_scored_records()
        cfg.min_post_count = 3  # no hashtag appears in all 3 posts
        trends = _rank_trends(records, scores, er, "hashtag", cfg)
        # '#ai' appears in 2 posts, '#python' in 2 posts — neither in 3
        assert all(t.post_count >= 3 for t in trends)

    def test_top_n_limit(self):
        records, scores, er, cfg = self._make_scored_records()
        cfg.min_post_count = 1
        cfg.top_n = 1
        trends = _rank_trends(records, scores, er, "hashtag", cfg)
        assert len(trends) <= 1


# ---------------------------------------------------------------------------
# Full analyse() integration
# ---------------------------------------------------------------------------


class TestAnalyse:
    def _records(self, n: int = 20) -> list:
        texts = [
            "#ai #python great content marketing platform launch",
            "#startup #growth hacking strategy product launch marketing",
            "#python data science analysis model training content",
        ]
        return [
            _make_record(
                post_id=f"R{i}",
                text=texts[i % len(texts)],
                days_ago=(i % 25) + 1,
                platform=["twitter", "instagram", "linkedin"][i % 3],
            )
            for i in range(n)
        ]

    def test_returns_analysis_result(self):
        from social_analyzer.analysis import AnalysisResult
        records = self._records()
        result = analyse(records)
        assert isinstance(result, AnalysisResult)

    def test_total_posts(self):
        records = self._records(10)
        cfg = AnalysisConfig(window_days=0)
        result = analyse(records, cfg)
        assert result.total_posts == 10

    def test_platform_metrics_present(self):
        records = self._records()
        result = analyse(records, AnalysisConfig(window_days=0))
        assert len(result.platform_metrics) > 0

    def test_top_hashtags_present(self):
        records = self._records(30)
        result = analyse(records, AnalysisConfig(window_days=0, min_post_count=1))
        assert len(result.top_hashtags) > 0

    def test_growth_insights_generated(self):
        records = self._records()
        result = analyse(records, AnalysisConfig(window_days=0))
        assert len(result.growth_insights) > 0

    def test_summary_non_empty(self):
        records = self._records()
        result = analyse(records, AnalysisConfig(window_days=0))
        assert len(result.summary) > 0

    def test_empty_records(self):
        result = analyse([])
        assert result.total_posts == 0
        assert result.summary == "No data available for analysis."
