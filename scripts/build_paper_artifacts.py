#!/usr/bin/env python3
"""Regenerate all paper-facing tables and figures from one evaluation run."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Complete evaluation result directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory; defaults to the input run directory",
    )
    parser.add_argument(
        "--format", choices=("pdf", "png"), default="pdf", help="Figure format"
    )
    parser.add_argument(
        "--no-refresh-summaries",
        action="store_true",
        help="Use existing derived CSVs instead of rebuilding them from raw_runs.csv",
    )
    return parser.parse_args()


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True)


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    run_dir = args.run_dir.resolve()
    output_dir = (args.output_dir or args.run_dir).resolve()

    if not args.no_refresh_summaries:
        run([sys.executable, str(script_dir / "summarize_results.py"), str(run_dir)])

    run(
        [
            sys.executable,
            str(script_dir / "build_tables.py"),
            str(run_dir),
            "--output-dir",
            str(output_dir),
        ]
    )
    run(
        [
            sys.executable,
            str(script_dir / "plot_results.py"),
            str(run_dir),
            "--output-dir",
            str(output_dir),
            "--format",
            args.format,
        ]
    )

    print(f"Paper artifacts written to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
