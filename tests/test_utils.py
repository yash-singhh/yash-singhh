"""Unit tests for social_analyzer.utils."""

import pytest
from collections import Counter

from social_analyzer.utils import (
    extract_hashtags,
    extract_keywords,
    count_frequencies,
    safe_divide,
    parse_timestamp,
)
from datetime import datetime, timezone


class TestExtractHashtags:
    def test_basic(self):
        assert extract_hashtags("Hello #World and #Python!") == ["world", "python"]

    def test_no_hashtags(self):
        assert extract_hashtags("No tags here") == []

    def test_empty_string(self):
        assert extract_hashtags("") == []

    def test_non_string(self):
        assert extract_hashtags(None) == []  # type: ignore[arg-type]

    def test_lowercase_normalisation(self):
        assert extract_hashtags("#AI #MachineLearning") == ["ai", "machinelearning"]

    def test_duplicate_hashtags(self):
        result = extract_hashtags("#ai #ai #python")
        assert result == ["ai", "ai", "python"]


class TestExtractKeywords:
    def test_basic(self):
        result = extract_keywords("Launch new product today")
        assert "launch" in result
        assert "product" in result

    def test_stop_words_removed(self):
        result = extract_keywords("the quick brown fox")
        assert "the" not in result

    def test_short_words_excluded(self):
        # Words with fewer than 3 characters are excluded by the regex `\b[a-z]{3,}\b`
        result = extract_keywords("go do it")
        assert result == []

    def test_non_string(self):
        assert extract_keywords(None) == []  # type: ignore[arg-type]

    def test_custom_stop_words(self):
        result = extract_keywords("apple banana cherry", stop_words={"banana"})
        assert "banana" not in result
        assert "apple" in result


class TestCountFrequencies:
    def test_empty(self):
        assert count_frequencies([]) == Counter()

    def test_basic(self):
        c = count_frequencies(["a", "b", "a", "c", "a"])
        assert c["a"] == 3
        assert c["b"] == 1

    def test_returns_counter(self):
        assert isinstance(count_frequencies(["x"]), Counter)


class TestSafeDivide:
    def test_normal(self):
        assert safe_divide(10, 4) == pytest.approx(2.5)

    def test_zero_denominator(self):
        assert safe_divide(10, 0) == 0.0

    def test_custom_default(self):
        assert safe_divide(5, 0, default=-1.0) == -1.0

    def test_float_result(self):
        assert isinstance(safe_divide(1, 3), float)


class TestParseTimestamp:
    def test_iso_with_tz(self):
        dt = parse_timestamp("2024-01-15T10:30:00+00:00")
        assert dt.year == 2024
        assert dt.tzinfo is not None

    def test_iso_without_tz(self):
        dt = parse_timestamp("2024-01-15T10:30:00")
        assert dt.tzinfo == timezone.utc

    def test_space_separated(self):
        dt = parse_timestamp("2024-03-17 08:00:00")
        assert dt.month == 3

    def test_date_only(self):
        dt = parse_timestamp("2024-06-01")
        assert dt.day == 1

    def test_datetime_passthrough(self):
        original = datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert parse_timestamp(original) == original

    def test_naive_datetime_gets_utc(self):
        naive = datetime(2024, 1, 1)
        result = parse_timestamp(naive)
        assert result.tzinfo == timezone.utc

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_timestamp("not-a-date")
