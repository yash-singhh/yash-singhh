"""Unit tests for social_analyzer.ingestion."""

import csv
import json
import pytest
from pathlib import Path

from social_analyzer.ingestion import load_file, PostRecord, IngestionResult, ALL_COLUMNS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_csv(tmp_path: Path, rows: list[dict], headers: list[str] | None = None) -> Path:
    """Helper: write a CSV file and return its path."""
    path = tmp_path / "posts.csv"
    hdrs = headers or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=hdrs, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_json(tmp_path: Path, data: list) -> Path:
    """Helper: write a JSON array file and return its path."""
    path = tmp_path / "posts.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


VALID_ROW = {
    "post_id": "P001",
    "platform": "Twitter",
    "timestamp": "2024-03-01 10:00:00",
    "text": "Hello #world",
    "likes": "100",
    "comments": "10",
    "shares": "5",
    "impressions": "2000",
    "clicks": "50",
    "followers": "5000",
}


# ---------------------------------------------------------------------------
# CSV tests
# ---------------------------------------------------------------------------


class TestLoadCSV:
    def test_valid_file(self, tmp_path):
        path = _write_csv(tmp_path, [VALID_ROW])
        result = load_file(path)
        assert isinstance(result, IngestionResult)
        assert len(result.records) == 1
        assert len(result.errors) == 0

    def test_record_fields(self, tmp_path):
        path = _write_csv(tmp_path, [VALID_ROW])
        record: PostRecord = load_file(path).records[0]
        assert record.post_id == "P001"
        assert record.platform == "twitter"  # normalised to lowercase
        assert record.likes == 100.0
        assert record.impressions == 2000.0

    def test_missing_required_column(self, tmp_path):
        row = {k: v for k, v in VALID_ROW.items() if k != "platform"}
        path = _write_csv(tmp_path, [row], headers=list(row.keys()))
        result = load_file(path)
        assert len(result.records) == 0
        assert len(result.errors) == 1

    def test_non_numeric_engagement(self, tmp_path):
        bad_row = dict(VALID_ROW, likes="not-a-number")
        path = _write_csv(tmp_path, [bad_row])
        result = load_file(path)
        assert len(result.errors) == 1
        assert "non-numeric" in result.errors[0][1].lower()

    def test_missing_numeric_defaults_to_zero(self, tmp_path):
        row = {k: v for k, v in VALID_ROW.items() if k not in ("clicks", "followers")}
        path = _write_csv(tmp_path, [row], headers=list(row.keys()))
        result = load_file(path)
        assert len(result.records) == 1
        assert result.records[0].clicks == 0.0
        assert result.records[0].followers == 0.0

    def test_bad_timestamp(self, tmp_path):
        bad_row = dict(VALID_ROW, timestamp="yesterday")
        path = _write_csv(tmp_path, [bad_row])
        result = load_file(path)
        assert len(result.errors) == 1

    def test_multiple_rows(self, tmp_path):
        rows = [dict(VALID_ROW, post_id=f"P{i:03d}") for i in range(5)]
        path = _write_csv(tmp_path, rows)
        result = load_file(path)
        assert len(result.records) == 5


# ---------------------------------------------------------------------------
# JSON tests
# ---------------------------------------------------------------------------


class TestLoadJSON:
    def test_valid_json_array(self, tmp_path):
        path = _write_json(tmp_path, [VALID_ROW])
        result = load_file(path)
        assert len(result.records) == 1
        assert len(result.errors) == 0

    def test_platform_normalised(self, tmp_path):
        row = dict(VALID_ROW, platform="Instagram")
        path = _write_json(tmp_path, [row])
        result = load_file(path)
        assert result.records[0].platform == "instagram"

    def test_missing_field_error(self, tmp_path):
        row = {k: v for k, v in VALID_ROW.items() if k != "text"}
        path = _write_json(tmp_path, [row])
        result = load_file(path)
        assert len(result.errors) == 1

    def test_numeric_values_as_ints(self, tmp_path):
        row = dict(VALID_ROW, likes=200, comments=20, shares=10)
        path = _write_json(tmp_path, [row])
        result = load_file(path)
        assert result.records[0].likes == 200.0


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


class TestLoadFileErrors:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_file(tmp_path / "nonexistent.csv")

    def test_unsupported_extension(self, tmp_path):
        path = tmp_path / "posts.xlsx"
        path.write_text("data")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            load_file(path)
