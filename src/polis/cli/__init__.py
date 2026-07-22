"""Thin command line interface for Polis analysis and correction examples."""

from __future__ import annotations

import argparse
import json
import sys
from io import TextIOWrapper
from pathlib import Path
from typing import cast

from polis import AnalysisResult, Analyzer, AnalyzerConfig, __version__
from polis.core import (
    AnalysisOptions,
    ConfigurationError,
    CorrectionSelectionError,
    PolisError,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polis",
        description="Polis analysis CLI",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="TOML configuration file for analysis defaults",
    )

    subparsers = parser.add_subparsers(dest="command")
    analyze = subparsers.add_parser("analyze", help="Analyze text and output findings")
    analyze.add_argument("text", nargs="?", help="Input text")
    analyze.add_argument(
        "--file",
        type=Path,
        help="Read input from UTF-8 encoded file",
    )
    analyze.add_argument(
        "--stdin",
        action="store_true",
        help="Read input from standard input",
    )
    analyze.add_argument(
        "--json",
        action="store_true",
        help="Render a JSON result",
    )
    analyze.add_argument(
        "--category",
        action="append",
        default=[],
        help="Filter findings by one category (repeatable)",
    )
    analyze.add_argument(
        "--minimum-confidence",
        type=float,
        default=None,
        help="Minimum confidence threshold (0.0 to 1.0)",
    )
    analyze.add_argument(
        "--apply",
        nargs="+",
        default=[],
        help="Explicit finding ids to apply to text",
    )
    return parser


def _parse_categories(value: list[str]) -> frozenset[str] | None:
    if not value:
        return None

    normalized: list[str] = []
    for item in value:
        for token in item.split(","):
            token = token.strip()
            if token:
                normalized.append(token)

    return frozenset(normalized)


def _read_input(
    *,
    stdin: bool,
    file_path: Path | None,
    positional: str | None,
) -> str:
    if stdin:
        return sys.stdin.read()

    if file_path is not None:
        return file_path.read_text(encoding="utf-8")

    if positional is not None:
        return positional

    raise ValueError("input is required via --stdin, --file, or positional text")


def _options_from_args(args: argparse.Namespace) -> AnalysisOptions:
    categories = _parse_categories(args.category)

    return AnalysisOptions(
        categories=categories,
        minimum_confidence=args.minimum_confidence or 0.0,
    )


def _render_json_output(result: AnalysisResult, applied_text: str | None = None) -> str:
    if applied_text is None:
        return cast(str, result.to_json())

    analysis_result_json = cast(dict[str, object], json.loads(result.to_json()))
    return json.dumps(
        {
            "analysis_result": analysis_result_json,
            "corrected_text": applied_text,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _render_human_output(result: AnalysisResult) -> str:
    lines: list[str] = []
    if not result.issues:
        return "No findings."

    for finding in result.issues:
        lines.append(
            f"{finding.id}\t{finding.category.value}\t{finding.severity.value}\t"
            f"{finding.message}\t{finding.source}\t{finding.confidence.value}"
        )
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "analyze":
        parser.error("the command must be 'analyze'")

    try:
        options = _options_from_args(args)
        text = _read_input(
            stdin=bool(args.stdin),
            file_path=args.file,
            positional=args.text,
        )

        analyzer = (
            Analyzer.from_config(args.config)
            if args.config
            else Analyzer(AnalyzerConfig())
        )
    except (ConfigurationError, OSError, ValueError, TypeError, PolisError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = analyzer.analyze(text, options=options)

    if args.apply:
        try:
            corrected = result.apply(tuple(args.apply))
        except CorrectionSelectionError as exc:
            print(f"error: {exc.code}:{exc.retryable}:{exc.context}", file=sys.stderr)
            return 1
        print(
            _render_json_output(result, corrected) if args.json else corrected,
        )
        return 0

    if args.json:
        print(_render_json_output(result))
    else:
        print(_render_human_output(result))
    return 0


def _configure_process_stdio() -> None:
    """Use the CLI's UTF-8 wire encoding on real process streams."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    _configure_process_stdio()
    raise SystemExit(run(argv))


if __name__ == "__main__":
    main()
