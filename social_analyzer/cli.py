"""Command-line interface for the social_analyzer package.

Usage examples
--------------
.. code-block:: bash

    # Analyse a CSV file with a 30-day window; save Markdown report
    python -m social_analyzer analyze --input data/posts.csv --window 30 --output reports/summary.md

    # JSON output
    python -m social_analyzer analyze --input data/posts.json --window 7 --output reports/summary.json

    # Use a custom YAML config
    python -m social_analyzer analyze --input data/posts.csv --config config/default_config.yaml

    # Print to stdout (no --output flag)
    python -m social_analyzer analyze --input data/posts.csv --format markdown

    # Check the data schema only (validate without analysing)
    python -m social_analyzer validate --input data/posts.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .analysis import AnalysisConfig, analyse
from .ingestion import load_file
from .reporting import build_report, save_report
from .utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_config(path: str | Path) -> dict:
    """Load a YAML or JSON config file and return a plain dict.

    Args:
        path: Path to the config file.

    Returns:
        Config dict (may be empty).
    """
    path = Path(path)
    if not path.exists():
        logger.warning("Config file not found: %s — using defaults.", path)
        return {}

    text = path.read_text(encoding="utf-8")
    ext = path.suffix.lower()

    if ext in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import]
            return yaml.safe_load(text) or {}
        except ImportError:
            logger.warning(
                "PyYAML is not installed; cannot parse %s.  "
                "Install it with:  pip install pyyaml",
                path,
            )
            return {}
    if ext == ".json":
        import json
        return json.loads(text) or {}

    logger.warning("Unrecognised config extension '%s'; using defaults.", ext)
    return {}


def _config_from_dict(d: dict) -> AnalysisConfig:
    """Build an :class:`~social_analyzer.analysis.AnalysisConfig` from a plain dict.

    Unrecognised keys are silently ignored.

    Args:
        d: Dict (typically loaded from a config file or CLI overrides).

    Returns:
        Populated :class:`~social_analyzer.analysis.AnalysisConfig`.
    """
    cfg = AnalysisConfig()
    if "window_days" in d:
        cfg.window_days = int(d["window_days"])
    if "top_n" in d:
        cfg.top_n = int(d["top_n"])
    if "rising_threshold" in d:
        cfg.rising_threshold = float(d["rising_threshold"])
    if "min_post_count" in d:
        cfg.min_post_count = int(d["min_post_count"])
    if "engagement_weight_likes" in d:
        cfg.engagement_weight_likes = float(d["engagement_weight_likes"])
    if "engagement_weight_comments" in d:
        cfg.engagement_weight_comments = float(d["engagement_weight_comments"])
    if "engagement_weight_shares" in d:
        cfg.engagement_weight_shares = float(d["engagement_weight_shares"])
    return cfg


# ---------------------------------------------------------------------------
# Sub-command: analyze
# ---------------------------------------------------------------------------


def cmd_analyze(args: argparse.Namespace) -> int:
    """Run the full analysis pipeline and output a report.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (``0`` on success, ``1`` on error).
    """
    # --- Set log level ---
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    # --- Load config ---
    cfg_dict: dict = {}
    if args.config:
        cfg_dict = _load_config(args.config)

    # CLI flags override config file
    if args.window is not None:
        cfg_dict["window_days"] = args.window
    if args.top_n is not None:
        cfg_dict["top_n"] = args.top_n

    analysis_config = _config_from_dict(cfg_dict)

    # --- Ingest ---
    try:
        result_ingest = load_file(args.input)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if result_ingest.errors:
        print(
            f"[WARN] {len(result_ingest.errors)} malformed row(s) skipped:",
            file=sys.stderr,
        )
        for row_num, msg in result_ingest.errors[:10]:
            print(f"  Row {row_num}: {msg}", file=sys.stderr)
        if len(result_ingest.errors) > 10:
            print(
                f"  … and {len(result_ingest.errors) - 10} more.",
                file=sys.stderr,
            )

    if not result_ingest.records:
        print("[ERROR] No valid records to analyse.", file=sys.stderr)
        return 1

    print(
        f"[INFO] Loaded {len(result_ingest.records)} records from {args.input}",
        file=sys.stderr,
    )

    # --- Analyse ---
    analysis_result = analyse(result_ingest.records, analysis_config)

    # --- Report ---
    fmt = args.format or _infer_format(args.output)
    if args.output:
        out_path = save_report(analysis_result, args.output, fmt=fmt)
        print(f"[INFO] Report saved → {out_path}")
    else:
        print(build_report(analysis_result, fmt=fmt))

    return 0


def _infer_format(output: Optional[str]) -> str:
    """Infer format from file extension; default to ``markdown``."""
    if not output:
        return "markdown"
    ext = Path(output).suffix.lower()
    return {".json": "json", ".csv": "csv", ".md": "markdown", ".markdown": "markdown"}.get(
        ext, "markdown"
    )


# ---------------------------------------------------------------------------
# Sub-command: validate
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate an input file and report schema errors without running analysis.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (``0`` = no errors, ``1`` = errors found or file not found).
    """
    logging.basicConfig(level=logging.WARNING)

    try:
        result = load_file(args.input)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"File   : {result.source}")
    print(f"Records: {len(result.records)}")
    print(f"Errors : {len(result.errors)}")

    if result.errors:
        print("\nMalformed rows:")
        for row_num, msg in result.errors:
            print(f"  Row {row_num}: {msg}")
        return 1

    print("\n✔ All rows are valid.")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="social_analyzer",
        description="Social-media analyst: analyse trends and grow your business.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version="social_analyzer 1.0.0"
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ---- analyze ----
    p_analyze = sub.add_parser(
        "analyze",
        help="Run trend analysis and generate a report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_analyze.add_argument(
        "--input", "-i", required=True, metavar="PATH",
        help="Path to the input CSV or JSON data file.",
    )
    p_analyze.add_argument(
        "--output", "-o", default=None, metavar="PATH",
        help="Output file path.  If omitted, the report is printed to stdout.",
    )
    p_analyze.add_argument(
        "--format", "-f", default=None,
        choices=["json", "csv", "markdown", "md"],
        help="Output format.  Inferred from --output extension when not set.",
    )
    p_analyze.add_argument(
        "--window", "-w", type=int, default=None, metavar="DAYS",
        help="Analysis window in days (0 = all data).  Overrides config file.",
    )
    p_analyze.add_argument(
        "--top-n", type=int, default=None, metavar="N",
        help="Number of top trends to include.  Overrides config file.",
    )
    p_analyze.add_argument(
        "--config", "-c", default=None, metavar="PATH",
        help="Path to YAML or JSON config file.",
    )
    p_analyze.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug-level logging.",
    )
    p_analyze.set_defaults(func=cmd_analyze)

    # ---- validate ----
    p_validate = sub.add_parser(
        "validate",
        help="Validate an input file's schema without running analysis.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_validate.add_argument(
        "--input", "-i", required=True, metavar="PATH",
        help="Path to the input CSV or JSON data file.",
    )
    p_validate.set_defaults(func=cmd_validate)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> int:
    """Parse *argv* and dispatch to the appropriate sub-command.

    Args:
        argv: Argument list (uses :data:`sys.argv` when *None*).

    Returns:
        Exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
