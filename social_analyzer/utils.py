"""Utility helpers shared across the social_analyzer package."""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable, List


def get_logger(name: str) -> logging.Logger:
    """Return a consistently configured module-level logger.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A :class:`logging.Logger` configured with a stream handler.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    return logger


def extract_hashtags(text: str) -> List[str]:
    """Extract all lowercase hashtags from *text*.

    Args:
        text: Raw post text.

    Returns:
        List of hashtags (with the leading ``#`` stripped).
    """
    if not isinstance(text, str):
        return []
    return [tag.lower() for tag in re.findall(r"#(\w+)", text)]


def extract_keywords(text: str, stop_words: Iterable[str] | None = None) -> List[str]:
    """Return significant lowercase words from *text*, excluding stop words.

    Args:
        text: Raw post text.
        stop_words: Words to exclude.  If *None*, a small built-in list is used.

    Returns:
        List of non-trivial keywords.
    """
    if not isinstance(text, str):
        return []

    default_stop = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "is", "it", "this", "that", "are", "was", "be", "as",
        "by", "from", "up", "about", "into", "then", "than", "so", "if",
        "we", "i", "you", "he", "she", "they", "my", "our", "your",
        "not", "can", "do", "has", "have", "had", "its", "their", "his", "her",
    }

    stop_set: set[str] = set(stop_words) if stop_words is not None else default_stop
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return [w for w in words if w not in stop_set]


def count_frequencies(items: Iterable[str]) -> Counter:
    """Count occurrences of each item in *items*.

    Args:
        items: Iterable of strings.

    Returns:
        A :class:`collections.Counter` mapping item → count.
    """
    return Counter(items)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide *numerator* by *denominator*, returning *default* on zero division.

    Args:
        numerator: Dividend.
        denominator: Divisor.
        default: Value returned when *denominator* is zero.

    Returns:
        Division result or *default*.
    """
    if denominator == 0:
        return default
    return numerator / denominator


def parse_timestamp(value: str | datetime) -> datetime:
    """Parse *value* into a timezone-aware :class:`~datetime.datetime`.

    Supported string formats: ISO-8601, ``%Y-%m-%d %H:%M:%S``, ``%Y-%m-%d``.

    Args:
        value: Timestamp string or :class:`~datetime.datetime`.

    Returns:
        Timezone-aware datetime (UTC).

    Raises:
        ValueError: When *value* cannot be parsed.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(str(value).strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {value!r}")
