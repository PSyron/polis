from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from polis.evaluation._synthetic_corpus_candidates import ErrorClass
from polis.evaluation._synthetic_corpus_distribution import (
    ERROR_CLASSES,
    ClassDistributionError,
)


def run() -> int:
    from polis.evaluation.synthetic_corpus import (
        SyntheticProfile,
        generate,
        write_artifacts,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=426)
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--profile", choices=("legacy", "validated"), default="legacy")
    parser.add_argument(
        "--class-quota",
        action="append",
        metavar="CLASS=COUNT",
        help="repeat once for each error class; quotas must sum to --count",
    )
    args = parser.parse_args()
    try:
        quota_items = cast(list[str] | None, args.class_quota)
        class_distribution = (
            parse_class_quotas(quota_items) if quota_items is not None else None
        )
        corpus = generate(
            seed=args.seed,
            count=args.count,
            profile=cast(SyntheticProfile, args.profile),
            class_distribution=class_distribution,
        )
    except (argparse.ArgumentTypeError, ClassDistributionError) as error:
        parser.error(str(error))
    manifest = write_artifacts(corpus, args.output, args.manifest)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


def parse_class_quotas(items: Sequence[str]) -> dict[ErrorClass, int]:
    distribution: dict[ErrorClass, int] = {}
    for item in items:
        error_class, separator, raw_quota = item.partition("=")
        if separator != "=" or error_class not in ERROR_CLASSES:
            msg = "--class-quota must use CLASS=COUNT for a supported error class"
            raise argparse.ArgumentTypeError(msg)
        try:
            quota = int(raw_quota)
        except ValueError as error:
            msg = "--class-quota COUNT must be an integer"
            raise argparse.ArgumentTypeError(msg) from error
        typed_error_class = cast(ErrorClass, error_class)
        if typed_error_class in distribution:
            msg = f"duplicate --class-quota for {typed_error_class}"
            raise argparse.ArgumentTypeError(msg)
        distribution[typed_error_class] = quota
    return distribution
