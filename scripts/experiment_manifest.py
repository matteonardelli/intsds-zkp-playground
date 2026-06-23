#!/usr/bin/env python3
"""Experimental matrix for the first policy-model campaign.

This module is the single source of truth for:
- canonical circuit configurations;
- policy labels used in the paper;
- scaling dimensions (bit-width and Merkle depth);
- monolithic compositions and their separate-proof baselines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence


BITS: tuple[int, ...] = (16, 32, 64)
MERKLE_DEPTHS: tuple[int, ...] = (8, 16, 32)
DEFAULT_SEED = 20260623


@dataclass(frozen=True)
class CircuitExperiment:
    """A circuit compiled and benchmarked as one proof."""

    name: str
    circuit_file: str
    family: str
    policy_set: str
    architecture: str
    role: str
    bits: Optional[int] = None
    merkle_depth: Optional[int] = None
    composition_id: Optional[str] = None

    @property
    def input_filename(self) -> str:
        return f"{self.name}.json"


@dataclass(frozen=True)
class SeparateProofBaseline:
    """A logical transaction enforced by multiple sequential proofs."""

    name: str
    family: str
    policy_set: str
    architecture: str
    components: tuple[str, ...]
    composition_id: str
    bits: Optional[int] = None
    merkle_depth: Optional[int] = None
    role: str = "composition_baseline"


ExperimentLike = CircuitExperiment | SeparateProofBaseline


def _individual_arithmetic() -> list[CircuitExperiment]:
    rows: list[CircuitExperiment] = []
    definitions = (
        (
            "local_financial_validity",
            "local_financial_validity_{bits}.circom",
            "pi_valid",
        ),
        (
            "operating_limit",
            "operating_limit_{bits}.circom",
            "pi_limit",
        ),
        (
            "privacy_budget",
            "privacy_budget_{bits}.circom",
            "pi_budget",
        ),
        (
            "state_transition_and_conservation",
            "state_transition_and_conservation_{bits}.circom",
            "pi_trans",
        ),
    )
    for family, circuit_pattern, policy_set in definitions:
        for bits in BITS:
            rows.append(
                CircuitExperiment(
                    name=f"{family}_{bits}",
                    circuit_file=circuit_pattern.format(bits=bits),
                    family=family,
                    policy_set=policy_set,
                    architecture="account",
                    role="individual_policy",
                    bits=bits,
                )
            )
    return rows


def _individual_membership() -> list[CircuitExperiment]:
    rows = [
        CircuitExperiment(
            name=f"merkle_membership_depth_{depth}",
            circuit_file=f"merkle_membership_depth_{depth}.circom",
            family="merkle_membership",
            policy_set="pi_mem",
            architecture="token",
            role="individual_policy",
            merkle_depth=depth,
        )
        for depth in MERKLE_DEPTHS
    ]
    rows.append(
        CircuitExperiment(
            name="nullifier_correctness_poseidon",
            circuit_file="nullifier_correctness_poseidon.circom",
            family="nullifier_correctness",
            policy_set="pi_mem",
            architecture="token",
            role="individual_policy",
        )
    )
    return rows


def _monolithic_compositions() -> list[CircuitExperiment]:
    rows: list[CircuitExperiment] = []

    for bits in BITS:
        rows.extend(
            [
                CircuitExperiment(
                    name=f"local_validity_and_operating_limit_{bits}",
                    circuit_file=f"local_validity_and_operating_limit_{bits}.circom",
                    family="local_validity_and_operating_limit",
                    policy_set="pi_valid+pi_limit",
                    architecture="account",
                    role="composition",
                    bits=bits,
                    composition_id=f"valid_limit_b{bits}",
                ),
                CircuitExperiment(
                    name=f"account_policy_core_{bits}",
                    circuit_file=f"account_policy_core_{bits}.circom",
                    family="account_policy_core",
                    policy_set="pi_valid+pi_trans+pi_limit",
                    architecture="account",
                    role="composition",
                    bits=bits,
                    composition_id=f"account_core_b{bits}",
                ),
                CircuitExperiment(
                    name=f"account_policy_with_privacy_budget_{bits}",
                    circuit_file=f"account_policy_with_privacy_budget_{bits}.circom",
                    family="account_policy_with_privacy_budget",
                    policy_set="pi_valid+pi_trans+pi_limit+pi_budget",
                    architecture="account",
                    role="composition",
                    bits=bits,
                    composition_id=f"account_budget_b{bits}",
                ),
            ]
        )

    for depth in MERKLE_DEPTHS:
        rows.append(
            CircuitExperiment(
                name=f"token_policy_bundle_32_depth_{depth}",
                circuit_file=f"token_policy_bundle_32_depth_{depth}.circom",
                family="token_policy_bundle",
                policy_set="pi_mem+pi_valid+pi_budget",
                architecture="token",
                role="composition",
                bits=32,
                merkle_depth=depth,
                composition_id=f"token_bundle_b32_d{depth}",
            )
        )

    return rows


def circuit_experiments() -> list[CircuitExperiment]:
    """Return the 28 monolithic circuit configurations in the first campaign."""
    return (
        _individual_arithmetic()
        + _individual_membership()
        + _monolithic_compositions()
    )


def separate_proof_baselines() -> list[SeparateProofBaseline]:
    rows: list[SeparateProofBaseline] = []

    for bits in BITS:
        rows.extend(
            [
                SeparateProofBaseline(
                    name=f"separate_valid_limit_{bits}",
                    family="local_validity_and_operating_limit",
                    policy_set="pi_valid+pi_limit",
                    architecture="account",
                    components=(
                        f"local_financial_validity_{bits}",
                        f"operating_limit_{bits}",
                    ),
                    composition_id=f"valid_limit_b{bits}",
                    bits=bits,
                ),
                SeparateProofBaseline(
                    name=f"separate_account_core_{bits}",
                    family="account_policy_core",
                    policy_set="pi_valid+pi_trans+pi_limit",
                    architecture="account",
                    components=(
                        f"local_financial_validity_{bits}",
                        f"state_transition_and_conservation_{bits}",
                        f"operating_limit_{bits}",
                    ),
                    composition_id=f"account_core_b{bits}",
                    bits=bits,
                ),
                SeparateProofBaseline(
                    name=f"separate_account_budget_{bits}",
                    family="account_policy_with_privacy_budget",
                    policy_set="pi_valid+pi_trans+pi_limit+pi_budget",
                    architecture="account",
                    components=(
                        f"local_financial_validity_{bits}",
                        f"state_transition_and_conservation_{bits}",
                        f"operating_limit_{bits}",
                        f"privacy_budget_{bits}",
                    ),
                    composition_id=f"account_budget_b{bits}",
                    bits=bits,
                ),
            ]
        )

    for depth in MERKLE_DEPTHS:
        rows.append(
            SeparateProofBaseline(
                name=f"separate_token_bundle_32_depth_{depth}",
                family="token_policy_bundle",
                policy_set="pi_mem+pi_valid+pi_budget",
                architecture="token",
                components=(
                    f"merkle_membership_depth_{depth}",
                    "nullifier_correctness_poseidon",
                    "local_financial_validity_32",
                    "privacy_budget_32",
                ),
                composition_id=f"token_bundle_b32_d{depth}",
                bits=32,
                merkle_depth=depth,
            )
        )

    return rows


def all_run_experiments(include_separate: bool = True) -> list[ExperimentLike]:
    rows: list[ExperimentLike] = list(circuit_experiments())
    if include_separate:
        rows.extend(separate_proof_baselines())
    return rows


def circuit_index() -> dict[str, CircuitExperiment]:
    return {row.name: row for row in circuit_experiments()}


def filter_experiments(
    rows: Sequence[ExperimentLike],
    names: Optional[Iterable[str]] = None,
    families: Optional[Iterable[str]] = None,
) -> list[ExperimentLike]:
    name_set = set(names or [])
    family_set = set(families or [])
    if not name_set and not family_set:
        return list(rows)
    return [
        row
        for row in rows
        if (not name_set or row.name in name_set)
        and (not family_set or row.family in family_set)
    ]


def input_path(project_root: Path, experiment_name: str) -> Path:
    return project_root / "inputs" / "valid" / f"{experiment_name}.json"
