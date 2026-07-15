#!/usr/bin/env python3
"""Run the policy-kernel benchmark campaign from the unified manifest.

The harness:
- uses the single matrix in experiment_manifest.py;
- supports core, extended, and complete paper campaign profiles;
- generates deterministic valid inputs when needed;
- compiles and sets up each unique circuit once;
- performs shuffled warm-up and measured rounds;
- records raw logical-run and component-run observations;
- keeps compilation/setup costs separate from transaction-path costs;
- supports monolithic circuits and sequential separate-proof baselines;
- enforces transaction-tag equality for security-consistent linked bundles.

Complete paper campaign:
    python scripts/run_bench.py --campaign paper

Focused extended composition campaign:
    python scripts/run_bench.py --campaign extended

Useful smoke test:
    python scripts/run_bench.py --campaign extended --repeats 3 --warmups 1 \
        --blocks 1 --force-rebuild
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from experiment_manifest import (
    CAMPAIGNS,
    DEFAULT_SEED,
    CircuitExperiment,
    ExperimentLike,
    SeparateProofBaseline,
    circuit_index,
    filter_experiments,
    input_path,
    logical_experiments,
)


@dataclass
class PreparedCircuit:
    spec: CircuitExperiment
    build_dir: Path
    base_name: str
    source_fingerprint: str
    r1cs: Path
    sym: Path
    wasm: Path
    witness_js: Path
    zkey_final: Path
    vkey_json: Path
    compile_cached: bool
    setup_cached: bool
    compile_time_s: Optional[float]
    setup_time_s: Optional[float]
    constraints: Optional[int]
    wires: Optional[int]
    public_inputs: Optional[int]
    private_inputs: Optional[int]
    outputs: Optional[int]
    r1cs_size_bytes: Optional[int]
    wasm_size_bytes: Optional[int]
    proving_key_size_bytes: Optional[int]
    verification_key_size_bytes: Optional[int]


@dataclass
class ComponentRunResult:
    witness_time_s: Optional[float]
    prove_time_s: Optional[float]
    verify_time_s: Optional[float]
    total_online_time_s: Optional[float]
    proof_size_bytes: Optional[int]
    public_size_bytes: Optional[int]
    verification_ok: bool
    binding_ok: Optional[bool]
    binding_value: str
    status: str
    error: str


class CommandError(RuntimeError):
    def __init__(self, cmd: Sequence[str], result: subprocess.CompletedProcess[str]):
        self.cmd = list(cmd)
        self.result = result
        message = (
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout: {result.stdout[-2000:]}\n"
            f"stderr: {result.stderr[-2000:]}"
        )
        super().__init__(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--campaign",
        choices=CAMPAIGNS,
        default="paper",
        help=(
            "Campaign profile: core (original matrix), extended (focused same-run RQ3 comparison), or paper (complete reproducibility run)."
        ),
    )
    parser.add_argument(
        "--proving-system",
        choices=("groth16", "plonk"),
        default="groth16",
        help="Groth16 is the default for the first campaign.",
    )
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--blocks", type=int, default=3)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--families",
        nargs="*",
        help="Optional family filter, e.g. local_financial_validity merkle_membership.",
    )
    parser.add_argument(
        "--experiments",
        nargs="*",
        help="Optional exact experiment-name filter.",
    )
    parser.add_argument(
        "--no-separate",
        action="store_true",
        help="Skip sequential separate-proof composition baselines.",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Delete matching fingerprinted build directories before compiling.",
    )
    parser.add_argument(
        "--no-generate-inputs",
        action="store_true",
        help="Do not invoke generate_inputs.js when input files are missing.",
    )
    parser.add_argument(
        "--run-id",
        help="Optional output directory name. A UTC timestamp is used by default.",
    )
    return parser.parse_args()


def ensure_positive_config(args: argparse.Namespace) -> None:
    if args.repeats <= 0:
        raise ValueError("--repeats must be positive")
    if args.warmups < 0:
        raise ValueError("--warmups cannot be negative")
    if args.blocks <= 0:
        raise ValueError("--blocks must be positive")
    if args.repeats % args.blocks != 0:
        raise ValueError("--repeats must be divisible by --blocks")


def run_command(
    cmd: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise CommandError(cmd, result)
    return result


def timed_command(
    cmd: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    check: bool = True,
) -> tuple[subprocess.CompletedProcess[str], float]:
    start = time.perf_counter()
    result = run_command(cmd, cwd=cwd, check=check)
    return result, time.perf_counter() - start


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise EnvironmentError(f"Required executable not found in PATH: {name}")


def command_version(cmd: Sequence[str]) -> Optional[str]:
    try:
        result = run_command(cmd, check=False)
    except OSError:
        return None
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0] if text else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_paths(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def optional_size(path: Path) -> Optional[int]:
    return path.stat().st_size if path.exists() else None


def git_commit(project_root: Path) -> Optional[str]:
    result = run_command(
        ["git", "rev-parse", "HEAD"], cwd=project_root, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def linux_cpu_model() -> Optional[str]:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return platform.processor() or None
    for line in cpuinfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor() or None


def memory_bytes() -> Optional[int]:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        return int(page_size * pages)
    except (AttributeError, ValueError, OSError):
        return None


def write_environment_metadata(
    output_path: Path,
    *,
    project_root: Path,
    ptaU_file: Path,
    args: argparse.Namespace,
    selected: Sequence[ExperimentLike],
) -> None:
    package_json = project_root / "package.json"
    package_lock = project_root / "package-lock.json"
    metadata: dict[str, Any] = {
        "run_id": output_path.parent.name,
        "campaign_profile": args.campaign,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "git_commit": git_commit(project_root),
        "source_tree_fingerprint": sha256_paths(
            project_root.glob("circuits/**/*.circom")
        ),
        "platform": platform.platform(),
        "python_version": sys.version,
        "node_version": command_version(["node", "--version"]),
        "circom_version": command_version(["circom", "--version"]),
        "snarkjs_version": command_version(["snarkjs", "--version"]),
        "cpu_model": linux_cpu_model(),
        "logical_cpu_count": os.cpu_count(),
        "physical_memory_bytes": memory_bytes(),
        "proving_system": args.proving_system,
        "warmups": args.warmups,
        "repeats": args.repeats,
        "blocks": args.blocks,
        "seed": args.seed,
        "separate_proof_baselines": not args.no_separate,
        "binding_scheme": {
            "hash": "Poseidon",
            "bundle_rule": "all component proofs verify and expose the same tx_tag",
            "applies_to": "experiments with binding_mode=tx_tag",
        },
        "ptau_file": str(ptaU_file),
        "ptau_sha256": sha256_file(ptaU_file),
        "package_json_sha256": sha256_file(package_json)
        if package_json.exists()
        else None,
        "package_lock_sha256": sha256_file(package_lock)
        if package_lock.exists()
        else None,
        "selected_experiments": [row.name for row in selected],
    }
    output_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def ensure_inputs(
    project_root: Path,
    required_circuits: Sequence[CircuitExperiment],
    seed: int,
    no_generate: bool,
) -> None:
    missing = [
        input_path(project_root, spec.name)
        for spec in required_circuits
        if not input_path(project_root, spec.name).exists()
    ]
    if missing and not no_generate:
        run_command(
            [
                "node",
                str(project_root / "scripts" / "generate_inputs.js"),
                "--out-dir",
                str(project_root / "inputs" / "valid"),
                "--seed",
                str(seed),
            ],
            cwd=project_root,
        )
        missing = [path for path in missing if not path.exists()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing benchmark inputs:\n{formatted}")


def source_fingerprint(project_root: Path, spec: CircuitExperiment) -> str:
    wrapper = project_root / "circuits" / spec.circuit_file
    templates = list((project_root / "circuits" / "templates").glob("**/*.circom"))
    return sha256_paths([wrapper, *templates])


def parse_r1cs_info(text: str) -> dict[str, Optional[int]]:
    patterns = {
        "wires": r"# of Wires:\s*(\d+)",
        "constraints": r"# of Constraints:\s*(\d+)",
        "private_inputs": r"# of Private Inputs:\s*(\d+)",
        "public_inputs": r"# of Public Inputs:\s*(\d+)",
        "outputs": r"# of Outputs:\s*(\d+)",
    }
    parsed: dict[str, Optional[int]] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        parsed[key] = int(match.group(1)) if match else None
    return parsed


def prepare_circuit(
    project_root: Path,
    spec: CircuitExperiment,
    proving_system: str,
    ptaU_file: Path,
    force_rebuild: bool,
) -> PreparedCircuit:
    circuit_path = project_root / "circuits" / spec.circuit_file
    if not circuit_path.exists():
        raise FileNotFoundError(f"Circuit not found: {circuit_path}")

    fingerprint = source_fingerprint(project_root, spec)
    build_dir = (
        project_root
        / "build"
        / proving_system
        / f"{spec.name}_{fingerprint[:12]}"
    )
    if force_rebuild and build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    base_name = circuit_path.stem
    wasm_dir = build_dir / f"{base_name}_js"
    r1cs = build_dir / f"{base_name}.r1cs"
    sym = build_dir / f"{base_name}.sym"
    wasm = wasm_dir / f"{base_name}.wasm"
    witness_js = wasm_dir / "generate_witness.js"
    zkey_initial = build_dir / f"{base_name}_0000.zkey"
    zkey_final = build_dir / f"{base_name}_final.zkey"
    vkey_json = build_dir / "verification_key.json"

    compile_cached = all(path.exists() for path in (r1cs, sym, wasm, witness_js))
    compile_time: Optional[float] = None
    if not compile_cached:
        _, compile_time = timed_command(
            [
                "circom",
                str(circuit_path),
                "--r1cs",
                "--wasm",
                "--sym",
                "-l",
                str(project_root / "node_modules"),
                "-o",
                str(build_dir),
            ],
            cwd=project_root,
        )

    setup_cached = zkey_final.exists() and vkey_json.exists()
    setup_time: Optional[float] = None
    if not setup_cached:
        setup_start = time.perf_counter()
        if proving_system == "groth16":
            run_command(
                [
                    "snarkjs",
                    "groth16",
                    "setup",
                    str(r1cs),
                    str(ptaU_file),
                    str(zkey_initial),
                ],
                cwd=project_root,
            )
            run_command(
                [
                    "snarkjs",
                    "zkey",
                    "contribute",
                    str(zkey_initial),
                    str(zkey_final),
                    f"--name=policy-bench-{spec.name}",
                    f"-e=policy-bench-{spec.name}-{fingerprint}",
                ],
                cwd=project_root,
            )
        else:
            run_command(
                [
                    "snarkjs",
                    "plonk",
                    "setup",
                    str(r1cs),
                    str(ptaU_file),
                    str(zkey_final),
                ],
                cwd=project_root,
            )
        run_command(
            [
                "snarkjs",
                "zkey",
                "export",
                "verificationkey",
                str(zkey_final),
                str(vkey_json),
            ],
            cwd=project_root,
        )
        setup_time = time.perf_counter() - setup_start

    info_result = run_command(
        ["snarkjs", "r1cs", "info", str(r1cs)], cwd=project_root
    )
    info = parse_r1cs_info(f"{info_result.stdout}\n{info_result.stderr}")

    return PreparedCircuit(
        spec=spec,
        build_dir=build_dir,
        base_name=base_name,
        source_fingerprint=fingerprint,
        r1cs=r1cs,
        sym=sym,
        wasm=wasm,
        witness_js=witness_js,
        zkey_final=zkey_final,
        vkey_json=vkey_json,
        compile_cached=compile_cached,
        setup_cached=setup_cached,
        compile_time_s=compile_time,
        setup_time_s=setup_time,
        constraints=info["constraints"],
        wires=info["wires"],
        public_inputs=info["public_inputs"],
        private_inputs=info["private_inputs"],
        outputs=info["outputs"],
        r1cs_size_bytes=optional_size(r1cs),
        wasm_size_bytes=optional_size(wasm),
        proving_key_size_bytes=optional_size(zkey_final),
        verification_key_size_bytes=optional_size(vkey_json),
    )


def verification_succeeded(result: subprocess.CompletedProcess[str]) -> bool:
    output = f"{result.stdout}\n{result.stderr}"
    return result.returncode == 0 and re.search(r"\bOK!?\b", output) is not None


def public_signal_index(sym_path: Path, signal_name: str) -> int:
    """Return the zero-based public.json position of a named main signal."""

    for line in sym_path.read_text(encoding="utf-8").splitlines():
        parts = line.split(",", 3)
        if len(parts) == 4 and parts[3] == signal_name:
            witness_index = int(parts[1])
            if witness_index <= 0:
                raise ValueError(
                    f"{signal_name} is not a public/main signal in {sym_path}"
                )
            return witness_index - 1
    raise ValueError(f"Could not locate {signal_name} in {sym_path}")


def expected_binding_value(project_root: Path, spec: CircuitExperiment) -> str:
    if not spec.binding_input_key:
        return ""
    payload = json.loads(input_path(project_root, spec.name).read_text(encoding="utf-8"))
    if spec.binding_input_key not in payload:
        raise KeyError(
            f"Missing binding input {spec.binding_input_key!r} for {spec.name}"
        )
    return str(payload[spec.binding_input_key])


def run_component(
    project_root: Path,
    prepared: PreparedCircuit,
    proving_system: str,
) -> ComponentRunResult:
    source_input = input_path(project_root, prepared.spec.name)
    try:
        with tempfile.TemporaryDirectory(
            prefix="run_", dir=str(prepared.build_dir)
        ) as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            witness = temp_dir / "witness.wtns"
            proof = temp_dir / "proof.json"
            public = temp_dir / "public.json"

            _, witness_time = timed_command(
                [
                    "node",
                    str(prepared.witness_js),
                    str(prepared.wasm),
                    str(source_input),
                    str(witness),
                ],
                cwd=project_root,
            )
            _, prove_time = timed_command(
                [
                    "snarkjs",
                    proving_system,
                    "prove",
                    str(prepared.zkey_final),
                    str(witness),
                    str(proof),
                    str(public),
                ],
                cwd=project_root,
            )
            verification, verify_time = timed_command(
                [
                    "snarkjs",
                    proving_system,
                    "verify",
                    str(prepared.vkey_json),
                    str(public),
                    str(proof),
                ],
                cwd=project_root,
                check=False,
            )
            cryptographic_ok = verification_succeeded(verification)

            binding_ok: Optional[bool] = None
            binding_value = ""
            if prepared.spec.binding_signal:
                signals = [
                    str(value)
                    for value in json.loads(public.read_text(encoding="utf-8"))
                ]
                index = public_signal_index(
                    prepared.sym, prepared.spec.binding_signal
                )
                binding_value = signals[index] if index < len(signals) else ""
                expected = expected_binding_value(project_root, prepared.spec)
                binding_ok = binding_value == expected

            component_ok = cryptographic_ok and binding_ok is not False
            if component_ok:
                status = "ok"
                error = ""
            elif not cryptographic_ok:
                status = "verification_failed"
                error = (verification.stderr or verification.stdout)[-2000:]
            else:
                status = "binding_output_mismatch"
                error = (
                    f"expected {prepared.spec.binding_input_key}="
                    f"{expected_binding_value(project_root, prepared.spec)}, "
                    f"observed {binding_value}"
                )

            return ComponentRunResult(
                witness_time_s=witness_time,
                prove_time_s=prove_time,
                verify_time_s=verify_time,
                total_online_time_s=witness_time + prove_time + verify_time,
                proof_size_bytes=optional_size(proof),
                public_size_bytes=optional_size(public),
                verification_ok=cryptographic_ok,
                binding_ok=binding_ok,
                binding_value=binding_value,
                status=status,
                error=error,
            )
    except Exception as exc:  # Keep failed observations in the raw dataset.
        return ComponentRunResult(
            witness_time_s=None,
            prove_time_s=None,
            verify_time_s=None,
            total_online_time_s=None,
            proof_size_bytes=None,
            public_size_bytes=None,
            verification_ok=False,
            binding_ok=False if prepared.spec.binding_signal else None,
            binding_value="",
            status="execution_failed",
            error=str(exc)[-4000:],
        )

def sum_optional(values: Iterable[Optional[float | int]]) -> Optional[float | int]:
    materialized = list(values)
    if any(value is None for value in materialized):
        return None
    return sum(value for value in materialized if value is not None)


def experiment_fields(row: ExperimentLike) -> dict[str, Any]:
    return {
        "experiment_name": row.name,
        "family": row.family,
        "policy_set": row.policy_set,
        "architecture": row.architecture,
        "role": row.role,
        "bits": row.bits,
        "merkle_depth": row.merkle_depth,
        "composition_id": row.composition_id,
        "comparison_group": row.comparison_group,
        "binding_mode": row.binding_mode,
    }


def execute_logical_run(
    *,
    project_root: Path,
    logical: ExperimentLike,
    prepared: dict[str, PreparedCircuit],
    proving_system: str,
    campaign_run_id: str,
    phase: str,
    block: int,
    repetition: int,
    order_index: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if isinstance(logical, CircuitExperiment):
        component_names = (logical.name,)
        execution_mode = "monolithic"
    else:
        component_names = logical.components
        execution_mode = "separate"

    component_results: list[tuple[str, ComponentRunResult]] = []
    for name in component_names:
        result = run_component(project_root, prepared[name], proving_system)
        component_results.append((name, result))

    proofs_ok = all(result.verification_ok for _, result in component_results)

    bundle_check_time_s = 0.0
    binding_ok: Optional[bool] = None
    if logical.binding_mode == "tx_tag":
        check_start = time.perf_counter()
        values = [result.binding_value for _, result in component_results]
        binding_ok = (
            all(result.binding_ok is True for _, result in component_results)
            and all(values)
            and len(set(values)) == 1
        )
        bundle_check_time_s = time.perf_counter() - check_start

    verification_ok = proofs_ok and binding_ok is not False
    status = "ok" if verification_ok else "failed"
    errors = " | ".join(
        f"{name}: {result.error}"
        for name, result in component_results
        if result.error
    )
    if proofs_ok and binding_ok is False:
        errors = (errors + " | " if errors else "") + "bundle tx_tag mismatch"

    component_total = sum_optional(
        result.total_online_time_s for _, result in component_results
    )
    total_online = (
        None
        if component_total is None
        else float(component_total) + bundle_check_time_s
    )

    base = {
        "campaign_run_id": campaign_run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "block": block,
        "repetition": repetition,
        "order_index": order_index,
        **experiment_fields(logical),
        "execution_mode": execution_mode,
        "component_count": len(component_names),
        "component_names": ";".join(component_names),
        "proving_system": proving_system,
        "constraints": sum_optional(
            prepared[name].constraints for name in component_names
        ),
        "witness_time_s": sum_optional(
            result.witness_time_s for _, result in component_results
        ),
        "prove_time_s": sum_optional(
            result.prove_time_s for _, result in component_results
        ),
        "verify_time_s": sum_optional(
            result.verify_time_s for _, result in component_results
        ),
        "bundle_check_time_s": bundle_check_time_s,
        "total_online_time_s": total_online,
        "proof_size_bytes": sum_optional(
            result.proof_size_bytes for _, result in component_results
        ),
        "public_size_bytes": sum_optional(
            result.public_size_bytes for _, result in component_results
        ),
        "proofs_ok": proofs_ok,
        "binding_ok": binding_ok,
        "verification_ok": verification_ok,
        "status": status,
        "error": errors,
    }

    component_rows: list[dict[str, Any]] = []
    for index, (name, result) in enumerate(component_results, start=1):
        result_dict = asdict(result)
        result_dict.pop("binding_value", None)
        component_rows.append(
            {
                "campaign_run_id": campaign_run_id,
                "timestamp_utc": base["timestamp_utc"],
                "phase": phase,
                "block": block,
                "repetition": repetition,
                "order_index": order_index,
                "parent_experiment": logical.name,
                "parent_execution_mode": execution_mode,
                "composition_id": logical.composition_id,
                "comparison_group": logical.comparison_group,
                "binding_mode": logical.binding_mode,
                "component_index": index,
                "component_name": name,
                "component_family": prepared[name].spec.family,
                "proving_system": proving_system,
                **result_dict,
            }
        )

    return base, component_rows

def write_artifacts_csv(
    output_path: Path, prepared: Sequence[PreparedCircuit], proving_system: str
) -> None:
    rows: list[dict[str, Any]] = []
    for item in prepared:
        row = {
            **experiment_fields(item.spec),
            "circuit_file": item.spec.circuit_file,
            "proving_system": proving_system,
            "source_fingerprint": item.source_fingerprint,
            "build_dir": str(item.build_dir),
            "compile_cached": item.compile_cached,
            "setup_cached": item.setup_cached,
            "compile_time_s": item.compile_time_s,
            "setup_time_s": item.setup_time_s,
            "constraints": item.constraints,
            "wires": item.wires,
            "public_inputs": item.public_inputs,
            "private_inputs": item.private_inputs,
            "outputs": item.outputs,
            "r1cs_size_bytes": item.r1cs_size_bytes,
            "wasm_size_bytes": item.wasm_size_bytes,
            "proving_key_size_bytes": item.proving_key_size_bytes,
            "verification_key_size_bytes": item.verification_key_size_bytes,
        }
        rows.append(row)
    write_csv(output_path, rows)


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def append_csv_row(
    writer: csv.DictWriter[str], stream: Any, row: dict[str, Any]
) -> None:
    writer.writerow(row)
    stream.flush()


def required_circuit_specs(
    selected: Sequence[ExperimentLike],
) -> list[CircuitExperiment]:
    index = circuit_index()
    names: set[str] = set()
    for row in selected:
        if isinstance(row, CircuitExperiment):
            names.add(row.name)
        else:
            names.update(row.components)
    return [index[name] for name in sorted(names)]


def main() -> int:
    args = parse_args()
    ensure_positive_config(args)
    project_root = args.project_root.resolve()

    for tool in ("node", "circom", "snarkjs"):
        require_tool(tool)

    ptaU_file = project_root / "powersOfTau28_hez_final_15.ptau"
    if not ptaU_file.exists():
        raise FileNotFoundError(f"Powers of Tau file not found: {ptaU_file}")

    selected = filter_experiments(
        logical_experiments(
            args.campaign, include_separate=not args.no_separate
        ),
        names=args.experiments,
        families=args.families,
    )
    if not selected:
        raise ValueError("The experiment filters selected no configurations")

    required_specs = required_circuit_specs(selected)
    ensure_inputs(
        project_root,
        required_specs,
        args.seed,
        args.no_generate_inputs,
    )

    run_id = args.run_id or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    ) + f"_{args.campaign}_{args.proving_system}"
    output_dir = project_root / "results" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)

    write_environment_metadata(
        output_dir / "environment.json",
        project_root=project_root,
        ptaU_file=ptaU_file,
        args=args,
        selected=selected,
    )

    print(
        f"Campaign profile: {args.campaign}; preparing "
        f"{len(required_specs)} unique circuits..."
    )
    prepared_list: list[PreparedCircuit] = []
    for index, spec in enumerate(required_specs, start=1):
        print(f"  [{index}/{len(required_specs)}] {spec.name}")
        prepared_list.append(
            prepare_circuit(
                project_root,
                spec,
                args.proving_system,
                ptaU_file,
                args.force_rebuild,
            )
        )
    prepared = {item.spec.name: item for item in prepared_list}
    write_artifacts_csv(
        output_dir / "artifacts.csv", prepared_list, args.proving_system
    )

    raw_path = output_dir / "raw_runs.csv"
    component_path = output_dir / "component_runs.csv"
    raw_fieldnames = [
        "campaign_run_id",
        "timestamp_utc",
        "phase",
        "block",
        "repetition",
        "order_index",
        "experiment_name",
        "family",
        "policy_set",
        "architecture",
        "role",
        "bits",
        "merkle_depth",
        "composition_id",
        "comparison_group",
        "binding_mode",
        "execution_mode",
        "component_count",
        "component_names",
        "proving_system",
        "constraints",
        "witness_time_s",
        "prove_time_s",
        "verify_time_s",
        "bundle_check_time_s",
        "total_online_time_s",
        "proof_size_bytes",
        "public_size_bytes",
        "proofs_ok",
        "binding_ok",
        "verification_ok",
        "status",
        "error",
    ]
    component_fieldnames = [
        "campaign_run_id",
        "timestamp_utc",
        "phase",
        "block",
        "repetition",
        "order_index",
        "parent_experiment",
        "parent_execution_mode",
        "composition_id",
        "comparison_group",
        "binding_mode",
        "component_index",
        "component_name",
        "component_family",
        "proving_system",
        "witness_time_s",
        "prove_time_s",
        "verify_time_s",
        "total_online_time_s",
        "proof_size_bytes",
        "public_size_bytes",
        "verification_ok",
        "binding_ok",
        "status",
        "error",
    ]

    rng = random.Random(args.seed)
    with raw_path.open("w", newline="", encoding="utf-8") as raw_stream, component_path.open(
        "w", newline="", encoding="utf-8"
    ) as component_stream:
        raw_writer = csv.DictWriter(raw_stream, fieldnames=raw_fieldnames)
        component_writer = csv.DictWriter(
            component_stream, fieldnames=component_fieldnames
        )
        raw_writer.writeheader()
        component_writer.writeheader()

        print(f"Running {args.warmups} shuffled warm-up rounds...")
        for warmup in range(1, args.warmups + 1):
            order = list(selected)
            rng.shuffle(order)
            for order_index, logical in enumerate(order, start=1):
                print(
                    f"  warmup {warmup}/{args.warmups}: {logical.name}",
                    flush=True,
                )
                row, components = execute_logical_run(
                    project_root=project_root,
                    logical=logical,
                    prepared=prepared,
                    proving_system=args.proving_system,
                    campaign_run_id=run_id,
                    phase="warmup",
                    block=0,
                    repetition=warmup,
                    order_index=order_index,
                )
                if not row["verification_ok"]:
                    raise RuntimeError(
                        f"Warm-up failed for {logical.name}: {row['error']}"
                    )

        per_block = args.repeats // args.blocks
        print(
            f"Running {args.repeats} measured repetitions per configuration "
            f"in {args.blocks} blocks..."
        )
        global_rep = 0
        for block in range(1, args.blocks + 1):
            for _ in range(per_block):
                global_rep += 1
                order = list(selected)
                rng.shuffle(order)
                for order_index, logical in enumerate(order, start=1):
                    print(
                        f"  block {block}/{args.blocks}, rep "
                        f"{global_rep}/{args.repeats}: {logical.name}",
                        flush=True,
                    )
                    row, components = execute_logical_run(
                        project_root=project_root,
                        logical=logical,
                        prepared=prepared,
                        proving_system=args.proving_system,
                        campaign_run_id=run_id,
                        phase="measured",
                        block=block,
                        repetition=global_rep,
                        order_index=order_index,
                    )
                    append_csv_row(raw_writer, raw_stream, row)
                    for component_row in components:
                        append_csv_row(
                            component_writer, component_stream, component_row
                        )

    latest = project_root / "results" / f"latest_{args.campaign}"
    try:
        if latest.is_symlink() or latest.exists():
            if latest.is_dir() and not latest.is_symlink():
                raise OSError(
                    f"Cannot replace non-symlink directory used as latest: {latest}"
                )
            latest.unlink()
        latest.symlink_to(output_dir.name, target_is_directory=True)
    except OSError as exc:
        print(f"[WARN] Could not update results/latest symlink: {exc}")

    print(f"\nCampaign completed: {output_dir}")
    print(f"Raw logical runs: {raw_path}")
    print(f"Component runs:   {component_path}")
    print(f"Offline artifacts:{output_dir / 'artifacts.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
