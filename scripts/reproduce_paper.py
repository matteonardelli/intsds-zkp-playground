#!/usr/bin/env python3
"""Run the complete paper evaluation and generate all paper artifacts.

This is the canonical reproducibility entry point. A successful invocation
creates one result directory containing raw measurements, derived CSV files,
functional-validation results, LaTeX tables, and figures.

Example:
    python3 scripts/reproduce_paper.py

Small smoke test:
    python3 scripts/reproduce_paper.py --repeats 3 --warmups 1 --blocks 1
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from experiment_manifest import DEFAULT_SEED


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--run-id",
        help="Result-directory name; a UTC timestamp is used by default.",
    )
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--blocks", type=int, default=3)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Recompile and set up every circuit instead of using the build cache.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip functional circuit validation.",
    )
    parser.add_argument(
        "--no-generate-inputs",
        action="store_true",
        help="Fail rather than generate deterministic inputs when missing.",
    )
    parser.add_argument(
        "--figure-format",
        choices=("pdf", "png"),
        default="pdf",
    )
    return parser.parse_args()


def run(command: list[str], *, cwd: Path) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=str(cwd), check=True)


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    script_dir = Path(__file__).resolve().parent
    results_root = project_root / "results"
    results_root.mkdir(parents=True, exist_ok=True)

    run_id = args.run_id or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "_paper_groth16"
    )
    run_dir = results_root / run_id
    if run_dir.exists():
        raise FileExistsError(f"Result directory already exists: {run_dir}")

    with tempfile.TemporaryDirectory(prefix="trace_validation_") as tmp:
        validation_csv = Path(tmp) / "functional_validation.csv"

        if not args.skip_validation:
            validation_command = [
                sys.executable,
                str(script_dir / "validate_circuits.py"),
                "--project-root",
                str(project_root),
                "--scope",
                "all",
                "--output-file",
                str(validation_csv),
            ]
            if args.no_generate_inputs:
                validation_command.append("--no-generate-inputs")
            run(validation_command, cwd=project_root)

        benchmark_command = [
            sys.executable,
            str(script_dir / "run_bench.py"),
            "--project-root",
            str(project_root),
            "--scope",
            "all",
            "--proving-system",
            "groth16",
            "--repeats",
            str(args.repeats),
            "--warmups",
            str(args.warmups),
            "--blocks",
            str(args.blocks),
            "--seed",
            str(args.seed),
            "--run-id",
            run_id,
        ]
        if args.force_rebuild:
            benchmark_command.append("--force-rebuild")
        if args.no_generate_inputs:
            benchmark_command.append("--no-generate-inputs")
        run(benchmark_command, cwd=project_root)

        if validation_csv.exists():
            shutil.copy2(validation_csv, run_dir / "functional_validation.csv")

    run(
        [
            sys.executable,
            str(script_dir / "build_paper_artifacts.py"),
            str(run_dir),
            "--output-dir",
            str(run_dir),
            "--format",
            args.figure_format,
        ],
        cwd=project_root,
    )

    manifest = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_scope": "all",
        "proving_system": "groth16",
        "repeats": args.repeats,
        "warmups": args.warmups,
        "blocks": args.blocks,
        "seed": args.seed,
        "functional_validation": not args.skip_validation,
        "paper_artifacts": {
            "tables": "tables/",
            "figures": "figures/",
        },
    }
    (run_dir / "reproduction.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("\nComplete paper evaluation and artifacts written to:")
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
