"""Trend analysis and growth-insight engine.

Public API
----------
* :func:`analyse` — main entry point; returns an :class:`AnalysisResult`.
* :class:`AnalysisConfig` — configurable parameters (time window, thresholds).
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import calendar

from .ingestion import PostRecord
from .utils import (
    count_frequencies,
    extract_hashtags,
    extract_keywords,
    get_logger,
    safe_divide,
)

logger: logging.Logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class AnalysisConfig:
    """Parameters controlling the analysis.

    Attributes:
        window_days: Rolling look-back window in days.  ``0`` means "all data".
        top_n: How many top items to keep in ranked lists.
        rising_threshold: Minimum ratio of recent-to-older engagement to label
            a topic as *rising* (default ``1.2`` = 20 % uplift).
        min_post_count: Minimum posts a topic/keyword must appear in to be
            included in trend tables.
        engagement_weight_likes: Weight for likes when computing engagement score.
        engagement_weight_comments: Weight for comments.
        engagement_weight_shares: Weight for shares.
    """

    window_days: int = 30
    top_n: int = 10
    rising_threshold: float = 1.2
    min_post_count: int = 2
    engagement_weight_likes: float = 1.0
    engagement_weight_comments: float = 2.0
    engagement_weight_shares: float = 3.0


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TrendItem:
    """A single ranked trend (hashtag, keyword, or topic).

    Attributes:
        name: The trend label.
        post_count: Number of posts mentioning this trend.
        total_engagement: Weighted engagement sum across matching posts.
        avg_engagement_rate: Mean engagement rate (%) across matching posts.
        direction: ``"rising"``, ``"declining"``, or ``"stable"``.
    """

    name: str
    post_count: int
    total_engagement: float
    avg_engagement_rate: float
    direction: str = "stable"


@dataclass
class PlatformMetrics:
    """Aggregate KPIs for a single platform.

    Attributes:
        platform: Platform name.
        post_count: Total posts analysed.
        total_likes: Sum of likes.
        total_comments: Sum of comments.
        total_shares: Sum of shares.
        total_impressions: Sum of impressions.
        total_clicks: Sum of clicks.
        avg_engagement_rate: Mean engagement rate (%).
        avg_ctr: Mean click-through rate (%).
        follower_growth_rate: Estimated follower growth rate (%).
    """

    platform: str
    post_count: int = 0
    total_likes: float = 0.0
    total_comments: float = 0.0
    total_shares: float = 0.0
    total_impressions: float = 0.0
    total_clicks: float = 0.0
    avg_engagement_rate: float = 0.0
    avg_ctr: float = 0.0
    follower_growth_rate: float = 0.0


@dataclass
class GrowthInsight:
    """A single actionable recommendation.

    Attributes:
        category: Topic area (e.g. ``"posting_time"``).
        insight: Human-readable recommendation text.
        supporting_data: Optional dict of evidence/metrics behind the insight.
    """

    category: str
    insight: str
    supporting_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Complete output of an analysis run.

    Attributes:
        config: The :class:`AnalysisConfig` used.
        window_start: Earliest timestamp included.
        window_end: Latest timestamp included.
        total_posts: Number of posts analysed.
        platform_metrics: Per-platform KPI dict.
        top_hashtags: Ranked hashtag trends.
        top_keywords: Ranked keyword trends.
        best_posting_hours: ``{hour: avg_engagement_rate}`` dict (UTC hours).
        best_posting_days: ``{weekday_name: avg_engagement_rate}`` dict.
        growth_insights: Actionable recommendations list.
        summary: Brief plain-English summary paragraph.
    """

    config: AnalysisConfig
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    total_posts: int
    platform_metrics: Dict[str, PlatformMetrics]
    top_hashtags: List[TrendItem]
    top_keywords: List[TrendItem]
    best_posting_hours: Dict[int, float]
    best_posting_days: Dict[str, float]
    growth_insights: List[GrowthInsight]
    summary: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyse(
    records: List[PostRecord],
    config: Optional[AnalysisConfig] = None,
) -> AnalysisResult:
    """Analyse *records* and return a comprehensive :class:`AnalysisResult`.

    Args:
        records: List of validated :class:`~social_analyzer.ingestion.PostRecord`.
        config: Analysis parameters.  Uses :class:`AnalysisConfig` defaults if
            *None*.

    Returns:
        An :class:`AnalysisResult` with trends, KPIs, and insights.
    """
    if config is None:
        config = AnalysisConfig()

    if not records:
        logger.warning("No records to analyse.")
        return _empty_result(config)

    # Apply time-window filter
    windowed = _apply_window(records, config.window_days)
    logger.info(
        "Analysing %d/%d records within %d-day window.",
        len(windowed),
        len(records),
        config.window_days,
    )

    if not windowed:
        logger.warning("No records fall within the configured time window.")
        windowed = records  # Fall back to all data

    window_start = min(r.timestamp for r in windowed)
    window_end = max(r.timestamp for r in windowed)

    # Core computations
    platform_metrics = _compute_platform_metrics(windowed, config)
    engagement_scores = {r.post_id: _engagement_score(r, config) for r in windowed}
    er_by_post = {r.post_id: _engagement_rate(r) for r in windowed}

    top_hashtags = _rank_trends(
        windowed, engagement_scores, er_by_post, "hashtag", config
    )
    top_keywords = _rank_trends(
        windowed, engagement_scores, er_by_post, "keyword", config
    )

    best_hours = _best_posting_hours(windowed, er_by_post)
    best_days = _best_posting_days(windowed, er_by_post)

    # Half-window split for rising/declining detection
    half = config.window_days // 2 if config.window_days > 0 else 15
    for item in top_hashtags:
        item.direction = _trend_direction(
            item.name, windowed, engagement_scores, config, half, "hashtag"
        )
    for item in top_keywords:
        item.direction = _trend_direction(
            item.name, windowed, engagement_scores, config, half, "keyword"
        )

    insights = _generate_insights(
        windowed, platform_metrics, top_hashtags, best_hours, best_days, config
    )

    summary = _build_summary(windowed, platform_metrics, top_hashtags, insights)

    return AnalysisResult(
        config=config,
        window_start=window_start,
        window_end=window_end,
        total_posts=len(windowed),
        platform_metrics=platform_metrics,
        top_hashtags=top_hashtags,
        top_keywords=top_keywords,
        best_posting_hours=best_hours,
        best_posting_days=best_days,
        growth_insights=insights,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Internal helpers — metrics
# ---------------------------------------------------------------------------


def _engagement_score(record: PostRecord, config: AnalysisConfig) -> float:
    """Compute a weighted engagement score for a single post.

    Args:
        record: The post record.
        config: Weights from :class:`AnalysisConfig`.

    Returns:
        Non-negative float engagement score.
    """
    return (
        record.likes * config.engagement_weight_likes
        + record.comments * config.engagement_weight_comments
        + record.shares * config.engagement_weight_shares
    )


def _engagement_rate(record: PostRecord) -> float:
    """Return post engagement rate as a percentage.

    Engagement Rate = (likes + comments + shares) / impressions * 100.
    Falls back to (likes + comments + shares) / followers * 100 when
    impressions is zero.  Returns ``0.0`` when both are zero.

    Args:
        record: The post record.

    Returns:
        Engagement rate percentage [0, 100].
    """
    interactions = record.likes + record.comments + record.shares
    if record.impressions > 0:
        return safe_divide(interactions * 100.0, record.impressions)
    return safe_divide(interactions * 100.0, record.followers)


def _ctr(record: PostRecord) -> float:
    """Click-through rate = clicks / impressions * 100.

    Args:
        record: The post record.

    Returns:
        CTR percentage.
    """
    return safe_divide(record.clicks * 100.0, record.impressions)


# ---------------------------------------------------------------------------
# Internal helpers — windowing
# ---------------------------------------------------------------------------


def _apply_window(records: List[PostRecord], window_days: int) -> List[PostRecord]:
    """Return records within the last *window_days* days.

    When *window_days* is ``0`` all records are returned.

    Args:
        records: Full record list.
        window_days: Rolling window length in calendar days.

    Returns:
        Filtered list.
    """
    if window_days <= 0:
        return list(records)

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=window_days)
    return [r for r in records if r.timestamp >= cutoff]


# ---------------------------------------------------------------------------
# Internal helpers — platform metrics
# ---------------------------------------------------------------------------


def _compute_platform_metrics(
    records: List[PostRecord], config: AnalysisConfig
) -> Dict[str, PlatformMetrics]:
    """Aggregate KPIs grouped by platform.

    Args:
        records: Windowed post records.
        config: Analysis config (unused currently; kept for extensibility).

    Returns:
        Dict mapping platform name → :class:`PlatformMetrics`.
    """
    grouped: Dict[str, List[PostRecord]] = defaultdict(list)
    for r in records:
        grouped[r.platform].append(r)

    metrics: Dict[str, PlatformMetrics] = {}
    for platform, posts in grouped.items():
        pm = PlatformMetrics(platform=platform, post_count=len(posts))
        pm.total_likes = sum(p.likes for p in posts)
        pm.total_comments = sum(p.comments for p in posts)
        pm.total_shares = sum(p.shares for p in posts)
        pm.total_impressions = sum(p.impressions for p in posts)
        pm.total_clicks = sum(p.clicks for p in posts)

        er_values = [_engagement_rate(p) for p in posts]
        pm.avg_engagement_rate = statistics.mean(er_values) if er_values else 0.0

        ctr_values = [_ctr(p) for p in posts if p.impressions > 0]
        pm.avg_ctr = statistics.mean(ctr_values) if ctr_values else 0.0

        # Follower growth: (max - min) / min * 100
        followers_list = [p.followers for p in posts if p.followers > 0]
        if len(followers_list) >= 2:
            pm.follower_growth_rate = safe_divide(
                (max(followers_list) - min(followers_list)) * 100.0,
                min(followers_list),
            )

        metrics[platform] = pm
    return metrics


# ---------------------------------------------------------------------------
# Internal helpers — trend ranking
# ---------------------------------------------------------------------------


def _rank_trends(
    records: List[PostRecord],
    engagement_scores: Dict[str, float],
    er_by_post: Dict[str, float],
    kind: str,
    config: AnalysisConfig,
) -> List[TrendItem]:
    """Rank trends by total engagement and return the top-N list.

    Args:
        records: Windowed post records.
        engagement_scores: Mapping of post_id → engagement score.
        er_by_post: Mapping of post_id → engagement rate (%).
        kind: ``"hashtag"`` or ``"keyword"``.
        config: Analysis config for top-N and min-post-count thresholds.

    Returns:
        Sorted list of :class:`TrendItem` (highest engagement first).
    """
    term_posts: Dict[str, List[PostRecord]] = defaultdict(list)
    for r in records:
        tokens: List[str]
        if kind == "hashtag":
            tokens = extract_hashtags(r.text)
        else:
            tokens = list(set(extract_keywords(r.text)))  # deduplicate per post
        for token in tokens:
            term_posts[token].append(r)

    items: List[TrendItem] = []
    for term, posts in term_posts.items():
        if len(posts) < config.min_post_count:
            continue
        total_eng = sum(engagement_scores[p.post_id] for p in posts)
        avg_er = statistics.mean(er_by_post[p.post_id] for p in posts)
        items.append(
            TrendItem(
                name=term,
                post_count=len(posts),
                total_engagement=round(total_eng, 2),
                avg_engagement_rate=round(avg_er, 4),
            )
        )

    items.sort(key=lambda x: x.total_engagement, reverse=True)
    return items[: config.top_n]


# ---------------------------------------------------------------------------
# Internal helpers — posting-time analysis
# ---------------------------------------------------------------------------


def _best_posting_hours(
    records: List[PostRecord], er_by_post: Dict[str, float]
) -> Dict[int, float]:
    """Return average engagement rate per UTC hour (0–23).

    Args:
        records: Windowed post records.
        er_by_post: Mapping of post_id → engagement rate (%).

    Returns:
        Dict of ``{hour: avg_engagement_rate}``.
    """
    hour_er: Dict[int, List[float]] = defaultdict(list)
    for r in records:
        hour_er[r.timestamp.hour].append(er_by_post[r.post_id])
    return {h: round(statistics.mean(v), 4) for h, v in hour_er.items()}


def _best_posting_days(
    records: List[PostRecord], er_by_post: Dict[str, float]
) -> Dict[str, float]:
    """Return average engagement rate per weekday name.

    Args:
        records: Windowed post records.
        er_by_post: Mapping of post_id → engagement rate (%).

    Returns:
        Dict of ``{weekday_name: avg_engagement_rate}``.
    """
    day_er: Dict[str, List[float]] = defaultdict(list)
    for r in records:
        day_name = calendar.day_name[r.timestamp.weekday()]
        day_er[day_name].append(er_by_post[r.post_id])
    return {d: round(statistics.mean(v), 4) for d, v in day_er.items()}


# ---------------------------------------------------------------------------
# Internal helpers — trend direction
# ---------------------------------------------------------------------------


def _trend_direction(
    term: str,
    records: List[PostRecord],
    engagement_scores: Dict[str, float],
    config: AnalysisConfig,
    split_days: int,
    kind: str,
) -> str:
    """Classify a trend as rising, declining, or stable.

    Splits the window at *split_days* from the end and compares mean
    engagement scores in the two halves.

    Args:
        term: Hashtag or keyword to evaluate.
        records: Windowed post records.
        engagement_scores: Mapping of post_id → engagement score.
        config: Analysis config (for :attr:`~AnalysisConfig.rising_threshold`).
        split_days: Days back to use as the split point.
        kind: ``"hashtag"`` or ``"keyword"``.

    Returns:
        ``"rising"``, ``"declining"``, or ``"stable"``.
    """
    if not records:
        return "stable"

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=split_days)
    older: List[float] = []
    recent: List[float] = []

    for r in records:
        tokens: List[str]
        if kind == "hashtag":
            tokens = extract_hashtags(r.text)
        else:
            tokens = extract_keywords(r.text)

        if term in tokens:
            score = engagement_scores[r.post_id]
            if r.timestamp >= cutoff:
                recent.append(score)
            else:
                older.append(score)

    if not older or not recent:
        return "stable"

    ratio = safe_divide(statistics.mean(recent), statistics.mean(older))
    if ratio >= config.rising_threshold:
        return "rising"
    if ratio <= safe_divide(1.0, config.rising_threshold):
        return "declining"
    return "stable"


# ---------------------------------------------------------------------------
# Internal helpers — growth insights
# ---------------------------------------------------------------------------


def _generate_insights(
    records: List[PostRecord],
    platform_metrics: Dict[str, PlatformMetrics],
    top_hashtags: List[TrendItem],
    best_hours: Dict[int, float],
    best_days: Dict[str, float],
    config: AnalysisConfig,
) -> List[GrowthInsight]:
    """Generate actionable growth recommendations.

    Args:
        records: Windowed post records.
        platform_metrics: Per-platform KPI dicts.
        top_hashtags: Ranked hashtag trend list.
        best_hours: Hourly engagement data.
        best_days: Day-of-week engagement data.
        config: Analysis config.

    Returns:
        List of :class:`GrowthInsight` objects.
    """
    insights: List[GrowthInsight] = []

    # --- Best posting time ---
    if best_hours:
        best_hour = max(best_hours, key=best_hours.__getitem__)
        insights.append(
            GrowthInsight(
                category="posting_time",
                insight=(
                    f"Post at {best_hour:02d}:00 UTC to maximise engagement "
                    f"(avg engagement rate: {best_hours[best_hour]:.2f}%)."
                ),
                supporting_data={"best_hour_utc": best_hour, "hours": best_hours},
            )
        )

    if best_days:
        best_day = max(best_days, key=best_days.__getitem__)
        insights.append(
            GrowthInsight(
                category="posting_day",
                insight=(
                    f"Publish on {best_day} for highest engagement "
                    f"(avg engagement rate: {best_days[best_day]:.2f}%)."
                ),
                supporting_data={"best_day": best_day, "days": best_days},
            )
        )

    # --- Top hashtags ---
    rising_tags = [t for t in top_hashtags if t.direction == "rising"]
    if rising_tags:
        tag_names = ", ".join(f"#{t.name}" for t in rising_tags[:3])
        insights.append(
            GrowthInsight(
                category="trending_hashtags",
                insight=(
                    f"Incorporate these rising hashtags to ride current trends: "
                    f"{tag_names}."
                ),
                supporting_data={"rising_hashtags": [t.name for t in rising_tags]},
            )
        )

    # --- Platform performance ---
    if platform_metrics:
        best_platform = max(
            platform_metrics.values(), key=lambda pm: pm.avg_engagement_rate
        )
        if best_platform.avg_engagement_rate > 0:
            insights.append(
                GrowthInsight(
                    category="platform_focus",
                    insight=(
                        f"Focus content creation efforts on "
                        f"{best_platform.platform.title()}, which yields the highest "
                        f"average engagement rate "
                        f"({best_platform.avg_engagement_rate:.2f}%)."
                    ),
                    supporting_data={
                        "platform": best_platform.platform,
                        "avg_engagement_rate": best_platform.avg_engagement_rate,
                    },
                )
            )

    # --- CTR opportunity ---
    low_ctr_platforms = [
        pm for pm in platform_metrics.values()
        if pm.avg_ctr < 1.0 and pm.post_count >= 3
    ]
    if low_ctr_platforms:
        names = ", ".join(p.platform.title() for p in low_ctr_platforms)
        insights.append(
            GrowthInsight(
                category="ctr_improvement",
                insight=(
                    f"Click-through rate is below 1 % on {names}. "
                    "Add clear calls-to-action and trackable links to improve CTR."
                ),
                supporting_data={
                    "platforms": [p.platform for p in low_ctr_platforms],
                },
            )
        )

    # --- Engagement rate benchmark ---
    all_er = [_engagement_rate(r) for r in records]
    if all_er:
        avg_er = statistics.mean(all_er)
        if avg_er < 2.0:
            insights.append(
                GrowthInsight(
                    category="engagement_improvement",
                    insight=(
                        f"Overall engagement rate is {avg_er:.2f}% (below the 2% "
                        "benchmark). Experiment with interactive content such as "
                        "polls, questions, and contests to boost audience interaction."
                    ),
                    supporting_data={"overall_avg_engagement_rate": round(avg_er, 4)},
                )
            )
        else:
            insights.append(
                GrowthInsight(
                    category="engagement_strength",
                    insight=(
                        f"Strong overall engagement rate of {avg_er:.2f}% — above "
                        "the 2% benchmark. Maintain content quality and consistency."
                    ),
                    supporting_data={"overall_avg_engagement_rate": round(avg_er, 4)},
                )
            )

    return insights


# ---------------------------------------------------------------------------
# Internal helpers — summary
# ---------------------------------------------------------------------------


def _build_summary(
    records: List[PostRecord],
    platform_metrics: Dict[str, PlatformMetrics],
    top_hashtags: List[TrendItem],
    insights: List[GrowthInsight],
) -> str:
    """Compose a brief plain-English summary paragraph.

    Args:
        records: Windowed post records.
        platform_metrics: Per-platform KPI dict.
        top_hashtags: Ranked hashtag trend list.
        insights: Generated growth insights.

    Returns:
        Multi-sentence summary string.
    """
    total = len(records)
    platforms = ", ".join(sorted(platform_metrics.keys()))
    tags = ", ".join(f"#{t.name}" for t in top_hashtags[:5]) or "N/A"
    top_insight = insights[0].insight if insights else "No insights generated."

    return (
        f"Analysed {total} posts across {platforms or 'no platforms'}. "
        f"Top trending hashtags: {tags}. "
        f"Key recommendation: {top_insight}"
    )


def _empty_result(config: AnalysisConfig) -> AnalysisResult:
    """Return an empty :class:`AnalysisResult` when there are no records."""
    return AnalysisResult(
        config=config,
        window_start=None,
        window_end=None,
        total_posts=0,
        platform_metrics={},
        top_hashtags=[],
        top_keywords=[],
        best_posting_hours={},
        best_posting_days={},
        growth_insights=[],
        summary="No data available for analysis.",
    )
