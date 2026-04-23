#!/usr/bin/env python3
"""
Benchmark harness for Circom + snarkjs experiments.

Supports:
- Groth16
- PLONK

What it does:
- compiles Circom circuits
- runs setup (once per circuit)
- generates witnesses
- generates proofs
- verifies proofs
- collects timing and artifact metadata
- saves results to CSV

Recommended usage:
    python run_bench.py

Requirements:
- circom
- snarkjs
- python >= 3.9
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Optional


# =========================
# Configuration
# =========================

PROJECT_ROOT = Path(".").resolve()
CIRCUITS_DIR = PROJECT_ROOT / "circuits"
BUILD_DIR = PROJECT_ROOT / "build"
RESULTS_DIR = PROJECT_ROOT / "results"
PTAU_FILE = PROJECT_ROOT     / "powersOfTau28_hez_final_12.ptau"
CIRCOM_INCLUDE_DIR = PROJECT_ROOT / "node_modules"

# Choose: "groth16" or "plonk"
PROVING_SYSTEM = "groth16"

# Number of repetitions for timing witness/prove/verify
REPEATS = 5

# If True, rebuild everything from scratch
FORCE_REBUILD = False

# If True, remove per-run witness/proof artifacts after each run
CLEAN_INTERMEDIATE = True


@dataclass
class Experiment:
    """One benchmark configuration."""
    name: str
    circuit_file: str
    input_data: Dict[str, Any]
    tags: Dict[str, Any]


@dataclass
class BenchmarkResult:
    experiment_name: str
    circuit_file: str
    proving_system: str
    constraints: Optional[int]
    proof_size_bytes: Optional[int]
    public_size_bytes: Optional[int]
    compile_time_s: Optional[float]
    setup_time_s: Optional[float]
    witness_time_s_mean: float
    prove_time_s_mean: float
    verify_time_s_mean: float
    verification_ok: bool
    tags_json: str


# =========================
# Utilities
# =========================

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_cmd(
    cmd: List[str],
    cwd: Optional[Path] = None,
    capture_output: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a subprocess and optionally raise on failure."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=capture_output,
        text=True,
    )
    if check and result.returncode != 0:
        print("\n[ERROR] Command failed:")
        print(" ".join(cmd))
        print("\n[STDOUT]")
        print(result.stdout)
        print("\n[STDERR]")
        print(result.stderr)
        raise RuntimeError(f"Command failed with exit code {result.returncode}")
    return result


def timed_call(fn, *args, **kwargs):
    """Measure wall-clock time of a function call."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    end = time.perf_counter()
    return result, end - start
   

def file_size_bytes(path: Path) -> Optional[int]:
    return path.stat().st_size if path.exists() else None


def parse_constraints_from_snarkjs_info(output: str) -> Optional[int]:
    """
    Parse the number of constraints from `snarkjs r1cs info`.
    Output usually contains lines like:
      # of Constraints: 1234
    """
    match = re.search(r"# of Constraints:\s+(\d+)", output)
    if match:
        return int(match.group(1))
    return None


def check_dependencies() -> None:
    for tool in ("circom", "snarkjs", "node"):
        if shutil.which(tool) is None:
            raise EnvironmentError(f"Required tool not found in PATH: {tool}")

    if PROVING_SYSTEM not in {"groth16", "plonk"}:
        raise ValueError("PROVING_SYSTEM must be 'groth16' or 'plonk'")

    if not PTAU_FILE.exists():
        raise FileNotFoundError(
            f"PTAU file not found: {PTAU_FILE}\n"
            "Download or place a powersOfTau file there."
        )


# =========================
# Path helpers
# =========================

def build_paths_for_experiment(exp: Experiment) -> Dict[str, Path]:
    """
    Create stable paths for build artifacts associated with one experiment.
    """
    base_name = Path(exp.circuit_file).stem
    exp_build_dir = BUILD_DIR / f"{exp.name}_{PROVING_SYSTEM}"
    ensure_dir(exp_build_dir)

    wasm_dir = exp_build_dir / f"{base_name}_js"

    return {
        "exp_build_dir": exp_build_dir,
        "r1cs": exp_build_dir / f"{base_name}.r1cs",
        "sym": exp_build_dir / f"{base_name}.sym",
        "wasm_dir": wasm_dir,
        "wasm": wasm_dir / f"{base_name}.wasm",
        "witness_js": wasm_dir / "generate_witness.js",
        "wtns": exp_build_dir / "witness.wtns",
        "input_json": exp_build_dir / "input.json",
        "zkey_0000": exp_build_dir / f"{base_name}_0000.zkey",
        "zkey_final": exp_build_dir / f"{base_name}_final.zkey",
        "vkey_json": exp_build_dir / "verification_key.json",
        "proof_json": exp_build_dir / "proof.json",
        "public_json": exp_build_dir / "public.json",
    }


# =========================
# Pipeline steps
# =========================

def compile_circuit(exp: Experiment, paths: Dict[str, Path]) -> float:
    """
    Compile the Circom circuit if needed.
    """
  
    circuit_path = CIRCUITS_DIR / exp.circuit_file
    if not circuit_path.exists():
        raise FileNotFoundError(f"Circuit file not found: {circuit_path}")

    if (
        not FORCE_REBUILD
        and paths["r1cs"].exists()
        and paths["sym"].exists()
        and paths["wasm"].exists()
        and paths["witness_js"].exists()
    ):
        return 0.0

    ensure_dir(paths["exp_build_dir"])

    cmd = [
        "circom",
        str(circuit_path),
        "--r1cs",
        "--wasm",
        "--sym",
        "-l", 
        str(CIRCOM_INCLUDE_DIR),
        "-o",
        str(paths["exp_build_dir"]),
    ]
    _, elapsed = timed_call(run_cmd, cmd)
    return elapsed


def setup_prover(paths: Dict[str, Path]) -> float:
    """
    Run Groth16 or PLONK setup.
    """

    if not FORCE_REBUILD and paths["zkey_final"].exists() and paths["vkey_json"].exists():
        return 0.0
    
    if PROVING_SYSTEM != "groth16" and PROVING_SYSTEM != "plonk":
        raise ValueError(f"Unsupported proving system: {PROVING_SYSTEM}")
        
    zkey = str(paths["zkey_final"])
    if PROVING_SYSTEM == "groth16":
        zkey =  str(paths["zkey_0000"])
        
    _, t_setup = timed_call(
        run_cmd,
        [
            "snarkjs",
            PROVING_SYSTEM,
            "setup",
            str(paths["r1cs"]),
            str(PTAU_FILE),
            zkey,
        ],
    )
     
    t_contrib = 0
    if PROVING_SYSTEM == "groth16":
        # Phase 2 setup (only for Groth16)
        # Contribute deterministic entropy for reproducibility
        # (fine for experiments; not for production trust assumptions)
        _, t_contrib = timed_call(
            run_cmd,
            [
                "snarkjs",
                "zkey",
                "contribute",
                str(paths["zkey_0000"]),
                str(paths["zkey_final"]),
                "--name=bench_contrib",
                "-e=benchmark_entropy",
            ],
        )

    # Export verification key
    _, t_vkey = timed_call(
        run_cmd,
        [
            "snarkjs",
            "zkey",
            "export",
            "verificationkey",
            str(paths["zkey_final"]),
            str(paths["vkey_json"]),
        ],
    )

    return t_setup + t_contrib + t_vkey


def get_constraint_count(paths: Dict[str, Path]) -> Optional[int]:
    """
    Extract number of constraints from snarkjs r1cs info.
    """
    result = run_cmd(
        ["snarkjs", "r1cs", "info", str(paths["r1cs"])],
        capture_output=True,
        check=True,
    )
    return parse_constraints_from_snarkjs_info(result.stdout + "\n" + result.stderr)


def write_input_json(paths: Dict[str, Path], input_data: Dict[str, Any]) -> None:
    with open(paths["input_json"], "w", encoding="utf-8") as f:
        json.dump(input_data, f, indent=2)


def generate_witness(paths: Dict[str, Path]) -> float:
    """
    Generate witness using the JS witness calculator produced by Circom.
    """
    if not paths["witness_js"].exists():
        raise FileNotFoundError(f"Missing witness generator: {paths['witness_js']}")

    cmd = [
        "node",
        str(paths["witness_js"]),
        str(paths["wasm"]),
        str(paths["input_json"]),
        str(paths["wtns"]),
    ]
    _, elapsed = timed_call(run_cmd, cmd)
    return elapsed


def generate_proof(paths: Dict[str, Path]) -> float:
    """
    Generate Groth16 proof.
    """
    cmd = [
        "snarkjs",
        PROVING_SYSTEM,
        "prove",
        str(paths["zkey_final"]),
        str(paths["wtns"]),
        str(paths["proof_json"]),
        str(paths["public_json"]),
    ]
    _, elapsed = timed_call(run_cmd, cmd)
    return elapsed


def verify_proof(paths: Dict[str, Path]) -> (bool, float):
    """
    Verify Groth16 proof.
    """
    cmd = [
        "snarkjs",
        PROVING_SYSTEM,
        "verify",
        str(paths["vkey_json"]),
        str(paths["public_json"]),
        str(paths["proof_json"]),
    ]
    result, elapsed = timed_call(run_cmd, cmd)
    out = (result.stdout + "\n" + result.stderr).lower()
    ok = "ok" in out
    return ok, elapsed


def cleanup_intermediate(paths: Dict[str, Path]) -> None:
    for key in ("wtns", "proof_json", "public_json", "input_json"):
        p = paths[key]
        if p.exists():
            p.unlink()


# =========================
# Benchmark logic
# =========================

def benchmark_experiment(exp: Experiment) -> BenchmarkResult:
    """
    Run full benchmark for one experiment.
    """
    print(f"\n=== Running experiment: {exp.name} [{PROVING_SYSTEM}] ===")
    paths = build_paths_for_experiment(exp)

    compile_time = compile_circuit(exp, paths)
    setup_time = setup_prover(paths)
    constraints = get_constraint_count(paths)

    witness_times: List[float] = []
    prove_times: List[float] = []
    verify_times: List[float] = []
    verification_ok = True

    for i in range(REPEATS):
        print(f"  repetition {i + 1}/{REPEATS}")
        write_input_json(paths, exp.input_data)

        wt = generate_witness(paths)
        witness_times.append(wt)

        pt = generate_proof(paths)
        prove_times.append(pt)

        ok, vt = verify_proof(paths)
        verify_times.append(vt)
        verification_ok = verification_ok and ok

        if CLEAN_INTERMEDIATE:
            cleanup_intermediate(paths)

    # Regenerate once for file size collection
    write_input_json(paths, exp.input_data)
    generate_witness(paths)
    generate_proof(paths)

    proof_size = file_size_bytes(paths["proof_json"])
    public_size = file_size_bytes(paths["public_json"])

    if CLEAN_INTERMEDIATE:
        cleanup_intermediate(paths)

    return BenchmarkResult(
        experiment_name=exp.name,
        circuit_file=exp.circuit_file,
        proving_system=PROVING_SYSTEM,
        constraints=constraints,
        proof_size_bytes=proof_size,
        public_size_bytes=public_size,
        compile_time_s=compile_time,
        setup_time_s=setup_time,
        witness_time_s_mean=median(witness_times),
        prove_time_s_mean=median(prove_times),
        verify_time_s_mean=median(verify_times),
        verification_ok=verification_ok,
        tags_json=json.dumps(exp.tags, sort_keys=True),
    )


def save_results_csv(results: List[BenchmarkResult], output_csv: Path) -> None:
    ensure_dir(output_csv.parent)
    if not results:
        return

    fieldnames = list(asdict(results[0]).keys())
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(asdict(row))


# =========================
# Experiment suite
# =========================

def build_experiments() -> List[Experiment]:
    experiments: List[Experiment] = []

    # ---- Sufficient Balance ----
    experiments.extend([
        Experiment(
            name="sufficient_balance_16",
            circuit_file="sufficient_balance_16.circom",
            input_data={"balance": 1000, "amount": 250},
            tags={"family": "sufficient_balance", "bits": 16, "class": "local"},
        ),
        Experiment(
            name="sufficient_balance_32",
            circuit_file="sufficient_balance_32.circom",
            input_data={"balance": 100000, "amount": 25000},
            tags={"family": "sufficient_balance", "bits": 32, "class": "local"},
        ),
        Experiment(
            name="sufficient_balance_64",
            circuit_file="sufficient_balance_64.circom",
            input_data={"balance": 1000000000, "amount": 250000000},
            tags={"family": "sufficient_balance", "bits": 64, "class": "local"},
        ),
    ])

    # ---- Cumulative Limit ----
    experiments.extend([
        Experiment(
            name="cumulative_limit_16",
            circuit_file="cumulative_limit_16.circom",
            input_data={"spent_window": 400, "amount": 100, "limit": 1000},
            tags={"family": "cumulative_limit", "bits": 16, "class": "cumulative"},
        ),
        Experiment(
            name="cumulative_limit_32",
            circuit_file="cumulative_limit_32.circom",
            input_data={"spent_window": 400000, "amount": 100000, "limit": 1000000},
            tags={"family": "cumulative_limit", "bits": 32, "class": "cumulative"},
        ),
        Experiment(
            name="cumulative_limit_64",
            circuit_file="cumulative_limit_64.circom",
            input_data={
                "spent_window": 400000000,
                "amount": 100000000,
                "limit": 1000000000,
            },
            tags={"family": "cumulative_limit", "bits": 64, "class": "cumulative"},
        ),
    ])

    # ---- Balance + Limit ----
    experiments.extend([
        Experiment(
            name="balance_and_limit_16",
            circuit_file="balance_and_limit_16.circom",
            input_data={
                "balance": 1000,
                "spent_window": 400,
                "amount": 100,
                "limit": 1000,
            },
            tags={"family": "balance_and_limit", "bits": 16, "class": "composed"},
        ),
        Experiment(
            name="balance_and_limit_32",
            circuit_file="balance_and_limit_32.circom",
            input_data={
                "balance": 1000000,
                "spent_window": 400000,
                "amount": 100000,
                "limit": 1000000,
            },
            tags={"family": "balance_and_limit", "bits": 32, "class": "composed"},
        ),
        Experiment(
            name="balance_and_limit_64",
            circuit_file="balance_and_limit_64.circom",
            input_data={
                "balance": 1000000000,
                "spent_window": 400000000,
                "amount": 100000000,
                "limit": 1000000000,
            },
            tags={"family": "balance_and_limit", "bits": 64, "class": "composed"},
        ),
    ])

    # ---- Balance + Limit + Conservation ----
    experiments.extend([
        Experiment(
            name="balance_limit_and_conservation_16",
            circuit_file="balance_limit_and_conservation_16.circom",
            input_data={
                "sender_balance": 1000,
                "receiver_balance": 300,
                "spent_window": 400,
                "sender_new": 900,
                "receiver_new": 400,
                "amount": 100,
                "limit": 1000,
            },
            tags={
                "family": "balance_limit_and_conservation",
                "bits": 16,
                "class": "stateful_composed",
            },
        ),
        Experiment(
            name="balance_limit_and_conservation_32",
            circuit_file="balance_limit_and_conservation_32.circom",
            input_data={
                "sender_balance": 1000000,
                "receiver_balance": 300000,
                "spent_window": 400000,
                "sender_new": 900000,
                "receiver_new": 400000,
                "amount": 100000,
                "limit": 1000000,
            },
            tags={
                "family": "balance_limit_and_conservation",
                "bits": 32,
                "class": "stateful_composed",
            },
        ),
        Experiment(
            name="balance_limit_and_conservation_64",
            circuit_file="balance_limit_and_conservation_64.circom",
            input_data={
                "sender_balance": 1000000000,
                "receiver_balance": 300000000,
                "spent_window": 400000000,
                "sender_new": 900000000,
                "receiver_new": 400000000,
                "amount": 100000000,
                "limit": 1000000000,
            },
            tags={
                "family": "balance_limit_and_conservation",
                "bits": 64,
                "class": "stateful_composed",
            },
        ),
    ])

    return experiments


# =========================
# Main
# =========================

def main() -> int:
    check_dependencies()
    ensure_dir(BUILD_DIR)
    ensure_dir(RESULTS_DIR)

    experiments = build_experiments()
    results: List[BenchmarkResult] = []

    for exp in experiments:
        try:
            result = benchmark_experiment(exp)
            results.append(result)
        except Exception as e:
            print(f"[FAIL] {exp.name}: {e}", file=sys.stderr)

    output_csv = RESULTS_DIR / f"bench_results_{PROVING_SYSTEM}.csv"
    save_results_csv(results, output_csv)

    print(f"\nSaved results to: {output_csv}")
    for r in results:
        print(
            f"- {r.experiment_name}: "
            f"system={r.proving_system}, "
            f"constraints={r.constraints}, "
            f"witness={r.witness_time_s_mean:.4f}s, "
            f"prove={r.prove_time_s_mean:.4f}s, "
            f"verify={r.verify_time_s_mean:.4f}s, "
            f"ok={r.verification_ok}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())