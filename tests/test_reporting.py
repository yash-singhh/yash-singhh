"""Unit tests for social_analyzer.reporting."""

import json
import csv
import io
import pytest
from pathlib import Path
from datetime import datetime, timezone

from social_analyzer.analysis import (
    AnalysisConfig,
    AnalysisResult,
    GrowthInsight,
    PlatformMetrics,
    TrendItem,
)
from social_analyzer.reporting import build_report, save_report


# ---------------------------------------------------------------------------
# Fixture: minimal AnalysisResult
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_result() -> AnalysisResult:
    return AnalysisResult(
        config=AnalysisConfig(),
        window_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2024, 3, 1, tzinfo=timezone.utc),
        total_posts=50,
        platform_metrics={
            "twitter": PlatformMetrics(
                platform="twitter",
                post_count=30,
                total_likes=3000,
                total_comments=500,
                total_shares=200,
                total_impressions=60000,
                total_clicks=1200,
                avg_engagement_rate=6.17,
                avg_ctr=2.0,
                follower_growth_rate=5.0,
            )
        },
        top_hashtags=[
            TrendItem("ai", 15, 4500.0, 7.5, "rising"),
            TrendItem("python", 12, 3000.0, 5.0, "stable"),
        ],
        top_keywords=[
            TrendItem("content", 18, 5000.0, 6.0, "rising"),
        ],
        best_posting_hours={9: 7.5, 17: 6.2, 12: 5.0},
        best_posting_days={"Monday": 7.1, "Friday": 6.5},
        growth_insights=[
            GrowthInsight(
                category="posting_time",
                insight="Post at 09:00 UTC for best results.",
                supporting_data={"best_hour_utc": 9},
            )
        ],
        summary="Analysed 50 posts. Top hashtag: #ai. Key tip: post at 09:00 UTC.",
    )


# ---------------------------------------------------------------------------
# JSON format
# ---------------------------------------------------------------------------


class TestJSONReport:
    def test_is_valid_json(self, minimal_result):
        output = build_report(minimal_result, fmt="json")
        data = json.loads(output)  # must not raise
        assert isinstance(data, dict)

    def test_meta_section(self, minimal_result):
        data = json.loads(build_report(minimal_result, fmt="json"))
        assert "meta" in data
        assert data["meta"]["total_posts"] == 50

    def test_platform_metrics_section(self, minimal_result):
        data = json.loads(build_report(minimal_result, fmt="json"))
        assert "platform_metrics" in data
        assert "twitter" in data["platform_metrics"]

    def test_top_hashtags_section(self, minimal_result):
        data = json.loads(build_report(minimal_result, fmt="json"))
        assert len(data["top_hashtags"]) == 2
        assert data["top_hashtags"][0]["name"] == "ai"

    def test_growth_insights_section(self, minimal_result):
        data = json.loads(build_report(minimal_result, fmt="json"))
        assert len(data["growth_insights"]) == 1
        assert data["growth_insights"][0]["category"] == "posting_time"

    def test_summary_present(self, minimal_result):
        data = json.loads(build_report(minimal_result, fmt="json"))
        assert "summary" in data
        assert len(data["summary"]) > 0


# ---------------------------------------------------------------------------
# CSV format
# ---------------------------------------------------------------------------


class TestCSVReport:
    def test_is_parseable(self, minimal_result):
        output = build_report(minimal_result, fmt="csv")
        # Should be non-empty and contain multiple sections
        assert "PLATFORM METRICS" in output
        assert "TOP HASHTAGS" in output

    def test_contains_platform_name(self, minimal_result):
        output = build_report(minimal_result, fmt="csv")
        assert "twitter" in output.lower()

    def test_contains_hashtag(self, minimal_result):
        output = build_report(minimal_result, fmt="csv")
        assert "#ai" in output


# ---------------------------------------------------------------------------
# Markdown format
# ---------------------------------------------------------------------------


class TestMarkdownReport:
    def test_has_headings(self, minimal_result):
        output = build_report(minimal_result, fmt="markdown")
        assert "# Social Media Analytics Report" in output

    def test_has_platform_table(self, minimal_result):
        output = build_report(minimal_result, fmt="markdown")
        assert "## Platform KPIs" in output
        assert "Twitter" in output

    def test_has_hashtag_table(self, minimal_result):
        output = build_report(minimal_result, fmt="markdown")
        assert "## Top Hashtags" in output
        assert "#ai" in output

    def test_direction_emoji(self, minimal_result):
        output = build_report(minimal_result, fmt="markdown")
        assert "📈" in output  # rising

    def test_growth_insights_section(self, minimal_result):
        output = build_report(minimal_result, fmt="markdown")
        assert "Growth Insights" in output

    def test_md_alias(self, minimal_result):
        assert build_report(minimal_result, fmt="md") == build_report(
            minimal_result, fmt="markdown"
        )


# ---------------------------------------------------------------------------
# Unknown format
# ---------------------------------------------------------------------------


class TestUnknownFormat:
    def test_raises_value_error(self, minimal_result):
        with pytest.raises(ValueError, match="Unknown report format"):
            build_report(minimal_result, fmt="xml")


# ---------------------------------------------------------------------------
# save_report
# ---------------------------------------------------------------------------


class TestSaveReport:
    def test_saves_json(self, tmp_path, minimal_result):
        out = tmp_path / "report.json"
        result = save_report(minimal_result, out)
        assert result.exists()
        data = json.loads(result.read_text())
        assert "meta" in data

    def test_saves_markdown(self, tmp_path, minimal_result):
        out = tmp_path / "report.md"
        save_report(minimal_result, out)
        content = out.read_text()
        assert "# Social Media Analytics Report" in content

    def test_saves_csv(self, tmp_path, minimal_result):
        out = tmp_path / "report.csv"
        save_report(minimal_result, out)
        assert "twitter" in out.read_text().lower()

    def test_creates_parent_dirs(self, tmp_path, minimal_result):
        out = tmp_path / "nested" / "deep" / "report.json"
        save_report(minimal_result, out)
        assert out.exists()

    def test_explicit_format_overrides_extension(self, tmp_path, minimal_result):
        out = tmp_path / "report.txt"  # unknown extension
        save_report(minimal_result, out, fmt="json")
        data = json.loads(out.read_text())
        assert "meta" in data

    def test_unknown_extension_raises(self, tmp_path, minimal_result):
        out = tmp_path / "report.xml"
        with pytest.raises(ValueError):
            save_report(minimal_result, out)
