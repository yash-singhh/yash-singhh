"""Reporting module — format and export :class:`AnalysisResult` objects.

Supported export formats
------------------------
* JSON  (``--format json``)
* CSV   (``--format csv``)
* Markdown (``--format markdown`` / ``--format md``)

The :func:`build_report` function returns a plain-text/JSON string, and
:func:`save_report` writes it to disk.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from .analysis import AnalysisResult, GrowthInsight, PlatformMetrics, TrendItem
from .utils import get_logger

logger: logging.Logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_report(result: AnalysisResult, fmt: str = "markdown") -> str:
    """Render *result* as a string in the requested format.

    Args:
        result: Analysis output to format.
        fmt: One of ``"json"``, ``"csv"``, ``"markdown"`` / ``"md"``.

    Returns:
        Formatted report string.

    Raises:
        ValueError: When *fmt* is not recognised.
    """
    fmt = fmt.lower().strip()
    if fmt == "json":
        return _to_json(result)
    if fmt == "csv":
        return _to_csv(result)
    if fmt in ("markdown", "md"):
        return _to_markdown(result)
    raise ValueError(
        f"Unknown report format '{fmt}'. Choose from: json, csv, markdown."
    )


def save_report(result: AnalysisResult, path: str | Path, fmt: str | None = None) -> Path:
    """Write *result* to *path*.

    The format is inferred from the file extension when *fmt* is ``None``.
    Supported extensions: ``.json``, ``.csv``, ``.md``, ``.markdown``.

    Args:
        result: Analysis output to save.
        path: Output file path (parent directories are created automatically).
        fmt: Explicit format string; overrides the extension-based inference.

    Returns:
        The resolved :class:`~pathlib.Path` of the written file.

    Raises:
        ValueError: When the format cannot be determined.
    """
    path = Path(path)
    if fmt is None:
        ext = path.suffix.lower()
        mapping = {".json": "json", ".csv": "csv", ".md": "markdown", ".markdown": "markdown"}
        fmt = mapping.get(ext)
        if fmt is None:
            raise ValueError(
                f"Cannot infer format from extension '{ext}'. "
                "Pass --format explicitly or use .json / .csv / .md"
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    content = build_report(result, fmt=fmt)
    path.write_text(content, encoding="utf-8")
    logger.info("Report saved to %s", path)
    return path


# ---------------------------------------------------------------------------
# JSON renderer
# ---------------------------------------------------------------------------


def _to_json(result: AnalysisResult) -> str:
    """Serialise *result* to a JSON string."""
    payload: Dict[str, Any] = {
        "meta": {
            "window_days": result.config.window_days,
            "window_start": _dt_str(result.window_start),
            "window_end": _dt_str(result.window_end),
            "total_posts": result.total_posts,
        },
        "platform_metrics": {
            platform: _pm_dict(pm)
            for platform, pm in result.platform_metrics.items()
        },
        "top_hashtags": [_trend_dict(t) for t in result.top_hashtags],
        "top_keywords": [_trend_dict(t) for t in result.top_keywords],
        "best_posting_hours": {str(k): v for k, v in result.best_posting_hours.items()},
        "best_posting_days": result.best_posting_days,
        "growth_insights": [_insight_dict(i) for i in result.growth_insights],
        "summary": result.summary,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _dt_str(dt: Any) -> str | None:
    return dt.isoformat() if dt is not None else None


def _pm_dict(pm: PlatformMetrics) -> Dict[str, Any]:
    return {
        "post_count": pm.post_count,
        "total_likes": pm.total_likes,
        "total_comments": pm.total_comments,
        "total_shares": pm.total_shares,
        "total_impressions": pm.total_impressions,
        "total_clicks": pm.total_clicks,
        "avg_engagement_rate_pct": round(pm.avg_engagement_rate, 4),
        "avg_ctr_pct": round(pm.avg_ctr, 4),
        "follower_growth_rate_pct": round(pm.follower_growth_rate, 4),
    }


def _trend_dict(t: TrendItem) -> Dict[str, Any]:
    return {
        "name": t.name,
        "post_count": t.post_count,
        "total_engagement": t.total_engagement,
        "avg_engagement_rate_pct": t.avg_engagement_rate,
        "direction": t.direction,
    }


def _insight_dict(i: GrowthInsight) -> Dict[str, Any]:
    return {
        "category": i.category,
        "insight": i.insight,
        "supporting_data": i.supporting_data,
    }


# ---------------------------------------------------------------------------
# CSV renderer
# ---------------------------------------------------------------------------


def _to_csv(result: AnalysisResult) -> str:
    """Serialise *result* to a multi-section CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    # --- Meta ---
    writer.writerow(["# META"])
    writer.writerow(["window_days", result.config.window_days])
    writer.writerow(["window_start", _dt_str(result.window_start)])
    writer.writerow(["window_end", _dt_str(result.window_end)])
    writer.writerow(["total_posts", result.total_posts])
    writer.writerow([])

    # --- Platform metrics ---
    writer.writerow(["# PLATFORM METRICS"])
    writer.writerow([
        "platform", "post_count", "total_likes", "total_comments",
        "total_shares", "total_impressions", "total_clicks",
        "avg_engagement_rate_pct", "avg_ctr_pct", "follower_growth_rate_pct",
    ])
    for platform, pm in result.platform_metrics.items():
        writer.writerow([
            platform, pm.post_count, pm.total_likes, pm.total_comments,
            pm.total_shares, pm.total_impressions, pm.total_clicks,
            round(pm.avg_engagement_rate, 4), round(pm.avg_ctr, 4),
            round(pm.follower_growth_rate, 4),
        ])
    writer.writerow([])

    # --- Top hashtags ---
    writer.writerow(["# TOP HASHTAGS"])
    writer.writerow(["rank", "hashtag", "post_count", "total_engagement",
                     "avg_engagement_rate_pct", "direction"])
    for rank, t in enumerate(result.top_hashtags, start=1):
        writer.writerow([rank, f"#{t.name}", t.post_count, t.total_engagement,
                         t.avg_engagement_rate, t.direction])
    writer.writerow([])

    # --- Top keywords ---
    writer.writerow(["# TOP KEYWORDS"])
    writer.writerow(["rank", "keyword", "post_count", "total_engagement",
                     "avg_engagement_rate_pct", "direction"])
    for rank, t in enumerate(result.top_keywords, start=1):
        writer.writerow([rank, t.name, t.post_count, t.total_engagement,
                         t.avg_engagement_rate, t.direction])
    writer.writerow([])

    # --- Best posting hours ---
    writer.writerow(["# BEST POSTING HOURS (UTC)"])
    writer.writerow(["hour_utc", "avg_engagement_rate_pct"])
    for hour, er in sorted(result.best_posting_hours.items()):
        writer.writerow([f"{hour:02d}:00", er])
    writer.writerow([])

    # --- Growth insights ---
    writer.writerow(["# GROWTH INSIGHTS"])
    writer.writerow(["category", "insight"])
    for ins in result.growth_insights:
        writer.writerow([ins.category, ins.insight])
    writer.writerow([])

    # --- Summary ---
    writer.writerow(["# SUMMARY"])
    writer.writerow([result.summary])

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------


def _to_markdown(result: AnalysisResult) -> str:
    """Serialise *result* to a Markdown string."""
    lines: List[str] = []

    lines.append("# Social Media Analytics Report\n")

    # --- Meta ---
    lines.append("## Overview\n")
    lines.append(f"| Parameter | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Analysis window | {result.config.window_days} days |")
    lines.append(f"| Window start | {_dt_str(result.window_start) or 'N/A'} |")
    lines.append(f"| Window end | {_dt_str(result.window_end) or 'N/A'} |")
    lines.append(f"| Total posts analysed | {result.total_posts} |")
    lines.append("")

    # --- Summary ---
    lines.append("## Executive Summary\n")
    lines.append(result.summary)
    lines.append("")

    # --- Platform metrics ---
    lines.append("## Platform KPIs\n")
    lines.append(
        "| Platform | Posts | Likes | Comments | Shares | Impressions | "
        "Avg ER % | Avg CTR % | Follower Growth % |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for pm in result.platform_metrics.values():
        lines.append(
            f"| {pm.platform.title()} | {pm.post_count} | {int(pm.total_likes)} | "
            f"{int(pm.total_comments)} | {int(pm.total_shares)} | "
            f"{int(pm.total_impressions)} | "
            f"{pm.avg_engagement_rate:.2f} | {pm.avg_ctr:.2f} | "
            f"{pm.follower_growth_rate:.2f} |"
        )
    lines.append("")

    # --- Top hashtags ---
    lines.append("## Top Hashtags\n")
    lines.append("| # | Hashtag | Posts | Total Engagement | Avg ER % | Direction |")
    lines.append("|---|---|---|---|---|---|")
    for rank, t in enumerate(result.top_hashtags, start=1):
        direction_emoji = {"rising": "📈", "declining": "📉", "stable": "➡️"}.get(
            t.direction, ""
        )
        lines.append(
            f"| {rank} | #{t.name} | {t.post_count} | {t.total_engagement:.1f} | "
            f"{t.avg_engagement_rate:.2f} | {direction_emoji} {t.direction} |"
        )
    lines.append("")

    # --- Top keywords ---
    lines.append("## Top Keywords\n")
    lines.append("| # | Keyword | Posts | Total Engagement | Avg ER % | Direction |")
    lines.append("|---|---|---|---|---|---|")
    for rank, t in enumerate(result.top_keywords, start=1):
        direction_emoji = {"rising": "📈", "declining": "📉", "stable": "➡️"}.get(
            t.direction, ""
        )
        lines.append(
            f"| {rank} | {t.name} | {t.post_count} | {t.total_engagement:.1f} | "
            f"{t.avg_engagement_rate:.2f} | {direction_emoji} {t.direction} |"
        )
    lines.append("")

    # --- Best posting times ---
    lines.append("## Best Posting Times (UTC)\n")
    if result.best_posting_hours:
        top_hours = sorted(
            result.best_posting_hours.items(), key=lambda x: x[1], reverse=True
        )[:5]
        lines.append("| Hour (UTC) | Avg ER % |")
        lines.append("|---|---|")
        for hour, er in top_hours:
            lines.append(f"| {hour:02d}:00 | {er:.2f} |")
    else:
        lines.append("_No posting-hour data available._")
    lines.append("")

    if result.best_posting_days:
        lines.append("### By Day of Week\n")
        top_days = sorted(
            result.best_posting_days.items(), key=lambda x: x[1], reverse=True
        )
        lines.append("| Day | Avg ER % |")
        lines.append("|---|---|")
        for day, er in top_days:
            lines.append(f"| {day} | {er:.2f} |")
        lines.append("")

    # --- Growth insights ---
    lines.append("## Growth Insights & Recommendations\n")
    for i, ins in enumerate(result.growth_insights, start=1):
        lines.append(f"**{i}. [{ins.category.replace('_', ' ').title()}]** {ins.insight}")
        lines.append("")

    return "\n".join(lines)
