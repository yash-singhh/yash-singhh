"""Data ingestion module — load and validate social-media post records.

Supported formats
-----------------
* CSV (any delimiter; auto-detected)
* JSON (array of objects **or** newline-delimited JSON)

Expected schema columns
-----------------------
Required:
    post_id, platform, timestamp, text

Optional (filled with ``0`` / empty string when absent):
    likes, comments, shares, impressions, clicks, followers
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .utils import get_logger, parse_timestamp

logger: logging.Logger = get_logger(__name__)

REQUIRED_COLUMNS: List[str] = ["post_id", "platform", "timestamp", "text"]
NUMERIC_COLUMNS: List[str] = [
    "likes",
    "comments",
    "shares",
    "impressions",
    "clicks",
    "followers",
]
ALL_COLUMNS: List[str] = REQUIRED_COLUMNS + NUMERIC_COLUMNS


@dataclass
class PostRecord:
    """A single validated social-media post record.

    Attributes:
        post_id: Unique post identifier.
        platform: Social platform name (e.g. ``"twitter"``, ``"instagram"``).
        timestamp: Publication time (timezone-aware).
        text: Post body text.
        likes: Number of likes/reactions.
        comments: Number of comments/replies.
        shares: Number of shares/retweets.
        impressions: Total impressions/views.
        clicks: Link clicks.
        followers: Follower count at post time.
        raw: Original raw dict from the data source.
    """

    post_id: str
    platform: str
    timestamp: Any  # datetime after validation
    text: str
    likes: float = 0.0
    comments: float = 0.0
    shares: float = 0.0
    impressions: float = 0.0
    clicks: float = 0.0
    followers: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class IngestionResult:
    """Outcome of a data ingestion run.

    Attributes:
        records: Successfully parsed :class:`PostRecord` objects.
        errors: ``(row_number, message)`` tuples for malformed rows.
        source: Path to the source file.
    """

    records: List[PostRecord]
    errors: List[Tuple[int, str]]
    source: Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_file(path: str | Path) -> IngestionResult:
    """Load posts from *path* (CSV or JSON).

    The file format is inferred from the ``.csv`` / ``.json`` extension
    (case-insensitive).

    Args:
        path: Filesystem path to the data file.

    Returns:
        An :class:`IngestionResult` with validated records and any errors.

    Raises:
        FileNotFoundError: When *path* does not exist.
        ValueError: When the file extension is not recognised.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    ext = path.suffix.lower()
    if ext == ".csv":
        return _load_csv(path)
    if ext == ".json":
        return _load_json(path)
    raise ValueError(
        f"Unsupported file extension '{ext}'.  Supported: .csv, .json"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_csv(path: Path) -> IngestionResult:
    """Load posts from a CSV file."""
    records: List[PostRecord] = []
    errors: List[Tuple[int, str]] = []

    with path.open(newline="", encoding="utf-8-sig") as fh:
        # Detect delimiter (comma vs tab vs semicolon)
        sample = fh.read(4096)
        fh.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        reader = csv.DictReader(fh, dialect=dialect)

        if reader.fieldnames is None:
            logger.warning("CSV file %s appears empty.", path)
            return IngestionResult(records=[], errors=[], source=path)

        fieldnames_lower = [f.strip().lower() for f in reader.fieldnames]

        for row_num, raw_row in enumerate(reader, start=2):  # 1-based; row 1 = header
            # Normalise keys to lowercase
            row: Dict[str, Any] = {
                k.strip().lower(): v.strip() if isinstance(v, str) else v
                for k, v in raw_row.items()
                if k is not None
            }
            record, error = _parse_row(row, row_num, fieldnames_lower)
            if error:
                errors.append((row_num, error))
                logger.debug("Row %d skipped: %s", row_num, error)
            else:
                assert record is not None
                records.append(record)

    logger.info(
        "CSV ingestion complete: %d records, %d errors  (%s)",
        len(records),
        len(errors),
        path.name,
    )
    return IngestionResult(records=records, errors=errors, source=path)


def _load_json(path: Path) -> IngestionResult:
    """Load posts from a JSON file (array or NDJSON)."""
    records: List[PostRecord] = []
    errors: List[Tuple[int, str]] = []

    raw_text = path.read_text(encoding="utf-8")

    # Try array first, then newline-delimited JSON
    rows: List[Dict[str, Any]] = []
    stripped = raw_text.strip()
    if stripped.startswith("["):
        try:
            rows = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON array in {path}: {exc}") from exc
    else:
        for line_num, line in enumerate(raw_text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append((line_num, f"JSON parse error: {exc}"))

    fieldnames_lower = list(ALL_COLUMNS)
    for row_num, raw_row in enumerate(rows, start=1):
        row = {k.strip().lower(): v for k, v in raw_row.items()}
        record, error = _parse_row(row, row_num, fieldnames_lower)
        if error:
            errors.append((row_num, error))
        else:
            assert record is not None
            records.append(record)

    logger.info(
        "JSON ingestion complete: %d records, %d errors  (%s)",
        len(records),
        len(errors),
        path.name,
    )
    return IngestionResult(records=records, errors=errors, source=path)


def _parse_row(
    row: Dict[str, Any],
    row_num: int,
    available_fields: List[str],
) -> Tuple[Optional[PostRecord], Optional[str]]:
    """Validate *row* and return ``(PostRecord, None)`` or ``(None, error_msg)``.

    Args:
        row: Normalised dict of field values.
        row_num: 1-based row number used for error messages.
        available_fields: Column names present in the source.

    Returns:
        A tuple of ``(record, error_message)``; exactly one will be ``None``.
    """
    # --- required fields ---
    missing = [col for col in REQUIRED_COLUMNS if not row.get(col)]
    if missing:
        return None, f"Missing required field(s): {missing}"

    # --- timestamp ---
    try:
        ts = parse_timestamp(row["timestamp"])
    except ValueError as exc:
        return None, str(exc)

    # --- numeric fields ---
    numeric: Dict[str, float] = {}
    for col in NUMERIC_COLUMNS:
        raw_val = row.get(col, "")
        if raw_val == "" or raw_val is None:
            numeric[col] = 0.0
        else:
            try:
                numeric[col] = float(str(raw_val).replace(",", ""))
            except (ValueError, TypeError):
                return None, f"Non-numeric value for '{col}': {raw_val!r}"

    record = PostRecord(
        post_id=str(row["post_id"]),
        platform=str(row["platform"]).lower().strip(),
        timestamp=ts,
        text=str(row.get("text", "")),
        likes=numeric["likes"],
        comments=numeric["comments"],
        shares=numeric["shares"],
        impressions=numeric["impressions"],
        clicks=numeric["clicks"],
        followers=numeric["followers"],
        raw=dict(row),
    )
    return record, None
