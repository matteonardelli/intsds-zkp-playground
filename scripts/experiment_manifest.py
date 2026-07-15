#!/usr/bin/env python3
"""Single source of truth for the policy-kernel benchmark campaign.

The manifest defines every circuit and logical experiment used in the paper:

* ``core``: individual kernels, original monolithic compositions, and the
  historical unbound separate-proof lower bounds;
* ``extended``: a focused RQ3 campaign that reruns the three representative
  legacy variants together with their security-consistent linked variants;
* ``paper``: the union of the complete core matrix and linked extension and
  therefore the complete reproducibility campaign.

No runner, validator, or summarizer maintains a second experimental matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional, Sequence


BITS: tuple[int, ...] = (16, 32, 64)
MERKLE_DEPTHS: tuple[int, ...] = (8, 16, 32)
DEFAULT_SEED = 20260623
CAMPAIGNS: tuple[str, ...] = ("core", "extended", "paper")

BindingMode = Literal["none", "shared_witness", "unbound", "tx_tag"]
ComparisonGroup = Literal["legacy", "linked"]


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
    comparison_group: Optional[ComparisonGroup] = None
    binding_mode: BindingMode = "none"
    binding_signal: Optional[str] = None
    binding_input_key: Optional[str] = None

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
    comparison_group: ComparisonGroup = "legacy"
    binding_mode: BindingMode = "unbound"


ExperimentLike = CircuitExperiment | SeparateProofBaseline


def _individual_arithmetic() -> list[CircuitExperiment]:
    rows: list[CircuitExperiment] = []
    definitions = (
        ("local_financial_validity", "local_financial_validity_{bits}.circom", "pi_valid"),
        ("operating_limit", "operating_limit_{bits}.circom", "pi_limit"),
        ("privacy_budget", "privacy_budget_{bits}.circom", "pi_budget"),
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


def _legacy_monolithic_compositions() -> list[CircuitExperiment]:
    """Original monolithic circuits, sound through a shared in-circuit witness."""

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
                    comparison_group="legacy",
                    binding_mode="shared_witness",
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
                    comparison_group="legacy",
                    binding_mode="shared_witness",
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
                    comparison_group="legacy",
                    binding_mode="shared_witness",
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
                comparison_group="legacy",
                binding_mode="shared_witness",
            )
        )
    return rows


def _legacy_separate_baselines() -> list[SeparateProofBaseline]:
    """Historical lower bounds with no cryptographic cross-proof binding."""

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


def _linked_circuits() -> list[CircuitExperiment]:
    """Circuits used by the security-consistent composition campaign."""

    common = {
        "comparison_group": "linked",
        "binding_mode": "tx_tag",
        "binding_signal": "main.tx_tag",
        "binding_input_key": "tx_tag",
    }
    return [
        CircuitExperiment(
            name="linked_valid_limit_monolithic_32",
            circuit_file="linked_valid_limit_monolithic_32.circom",
            family="local_validity_and_operating_limit",
            policy_set="pi_valid+pi_limit",
            architecture="account",
            role="composition",
            bits=32,
            composition_id="valid_limit_b32",
            **common,
        ),
        CircuitExperiment(
            name="linked_valid_limit_validity_32",
            circuit_file="linked_valid_limit_validity_32.circom",
            family="linked_valid_limit_component",
            policy_set="pi_valid+tx_binding",
            architecture="account",
            role="composition_component",
            bits=32,
            composition_id="valid_limit_b32",
            **common,
        ),
        CircuitExperiment(
            name="linked_valid_limit_limit_32",
            circuit_file="linked_valid_limit_limit_32.circom",
            family="linked_valid_limit_component",
            policy_set="pi_limit+tx_binding",
            architecture="account",
            role="composition_component",
            bits=32,
            composition_id="valid_limit_b32",
            **common,
        ),
        CircuitExperiment(
            name="linked_account_budget_monolithic_32",
            circuit_file="linked_account_budget_monolithic_32.circom",
            family="account_policy_with_privacy_budget",
            policy_set="pi_valid+pi_trans+pi_limit+pi_budget",
            architecture="account",
            role="composition",
            bits=32,
            composition_id="account_budget_b32",
            **common,
        ),
        CircuitExperiment(
            name="linked_account_budget_validity_32",
            circuit_file="linked_account_budget_validity_32.circom",
            family="linked_account_budget_component",
            policy_set="pi_valid+tx_binding",
            architecture="account",
            role="composition_component",
            bits=32,
            composition_id="account_budget_b32",
            **common,
        ),
        CircuitExperiment(
            name="linked_account_budget_transition_32",
            circuit_file="linked_account_budget_transition_32.circom",
            family="linked_account_budget_component",
            policy_set="pi_trans+tx_binding",
            architecture="account",
            role="composition_component",
            bits=32,
            composition_id="account_budget_b32",
            **common,
        ),
        CircuitExperiment(
            name="linked_account_budget_limit_32",
            circuit_file="linked_account_budget_limit_32.circom",
            family="linked_account_budget_component",
            policy_set="pi_limit+tx_binding",
            architecture="account",
            role="composition_component",
            bits=32,
            composition_id="account_budget_b32",
            **common,
        ),
        CircuitExperiment(
            name="linked_account_budget_budget_32",
            circuit_file="linked_account_budget_budget_32.circom",
            family="linked_account_budget_component",
            policy_set="pi_budget+tx_binding",
            architecture="account",
            role="composition_component",
            bits=32,
            composition_id="account_budget_b32",
            **common,
        ),
        CircuitExperiment(
            name="linked_token_bundle_monolithic_32_depth_16",
            circuit_file="linked_token_bundle_monolithic_32_depth_16.circom",
            family="token_policy_bundle",
            policy_set="pi_mem+pi_valid+pi_budget",
            architecture="token",
            role="composition",
            bits=32,
            merkle_depth=16,
            composition_id="token_bundle_b32_d16",
            **common,
        ),
        CircuitExperiment(
            name="linked_token_bundle_membership_32_depth_16",
            circuit_file="linked_token_bundle_membership_32_depth_16.circom",
            family="linked_token_bundle_component",
            policy_set="pi_mem_membership+tx_binding",
            architecture="token",
            role="composition_component",
            bits=32,
            merkle_depth=16,
            composition_id="token_bundle_b32_d16",
            **common,
        ),
        CircuitExperiment(
            name="linked_token_bundle_nullifier_32_depth_16",
            circuit_file="linked_token_bundle_nullifier_32_depth_16.circom",
            family="linked_token_bundle_component",
            policy_set="pi_mem_nullifier+tx_binding",
            architecture="token",
            role="composition_component",
            bits=32,
            merkle_depth=16,
            composition_id="token_bundle_b32_d16",
            **common,
        ),
        CircuitExperiment(
            name="linked_token_bundle_validity_32_depth_16",
            circuit_file="linked_token_bundle_validity_32_depth_16.circom",
            family="linked_token_bundle_component",
            policy_set="pi_valid+tx_binding",
            architecture="token",
            role="composition_component",
            bits=32,
            merkle_depth=16,
            composition_id="token_bundle_b32_d16",
            **common,
        ),
        CircuitExperiment(
            name="linked_token_bundle_budget_32_depth_16",
            circuit_file="linked_token_bundle_budget_32_depth_16.circom",
            family="linked_token_bundle_component",
            policy_set="pi_budget+tx_binding",
            architecture="token",
            role="composition_component",
            bits=32,
            merkle_depth=16,
            composition_id="token_bundle_b32_d16",
            **common,
        ),
    ]


def _linked_logical_experiments() -> list[ExperimentLike]:
    index = circuit_index()
    rows: list[ExperimentLike] = [
        index["linked_valid_limit_monolithic_32"],
        index["linked_account_budget_monolithic_32"],
        index["linked_token_bundle_monolithic_32_depth_16"],
    ]
    rows.extend(
        [
            SeparateProofBaseline(
                name="linked_separate_valid_limit_32",
                family="local_validity_and_operating_limit",
                policy_set="pi_valid+pi_limit",
                architecture="account",
                components=(
                    "linked_valid_limit_validity_32",
                    "linked_valid_limit_limit_32",
                ),
                composition_id="valid_limit_b32",
                bits=32,
                role="composition_baseline",
                comparison_group="linked",
                binding_mode="tx_tag",
            ),
            SeparateProofBaseline(
                name="linked_separate_account_budget_32",
                family="account_policy_with_privacy_budget",
                policy_set="pi_valid+pi_trans+pi_limit+pi_budget",
                architecture="account",
                components=(
                    "linked_account_budget_validity_32",
                    "linked_account_budget_transition_32",
                    "linked_account_budget_limit_32",
                    "linked_account_budget_budget_32",
                ),
                composition_id="account_budget_b32",
                bits=32,
                role="composition_baseline",
                comparison_group="linked",
                binding_mode="tx_tag",
            ),
            SeparateProofBaseline(
                name="linked_separate_token_bundle_32_depth_16",
                family="token_policy_bundle",
                policy_set="pi_mem+pi_valid+pi_budget",
                architecture="token",
                components=(
                    "linked_token_bundle_membership_32_depth_16",
                    "linked_token_bundle_nullifier_32_depth_16",
                    "linked_token_bundle_validity_32_depth_16",
                    "linked_token_bundle_budget_32_depth_16",
                ),
                composition_id="token_bundle_b32_d16",
                bits=32,
                merkle_depth=16,
                role="composition_baseline",
                comparison_group="linked",
                binding_mode="tx_tag",
            ),
        ]
    )
    return rows


def core_circuit_experiments() -> list[CircuitExperiment]:
    return _individual_arithmetic() + _individual_membership() + _legacy_monolithic_compositions()


def all_circuit_experiments() -> list[CircuitExperiment]:
    """Return every unique circuit referenced by any campaign."""

    return core_circuit_experiments() + _linked_circuits()


def circuit_index() -> dict[str, CircuitExperiment]:
    rows = all_circuit_experiments()
    index = {row.name: row for row in rows}
    if len(index) != len(rows):
        raise ValueError("Duplicate circuit names in experiment manifest")
    return index


def logical_experiments(
    campaign: str = "paper", *, include_separate: bool = True
) -> list[ExperimentLike]:
    """Return the logical experiments for a named campaign profile."""

    if campaign not in CAMPAIGNS:
        raise ValueError(f"Unknown campaign {campaign!r}; choose from {CAMPAIGNS}")

    core: list[ExperimentLike] = list(core_circuit_experiments())
    if include_separate:
        core.extend(_legacy_separate_baselines())

    linked = _linked_logical_experiments()
    if not include_separate:
        linked = [row for row in linked if isinstance(row, CircuitExperiment)]

    if campaign == "core":
        return core
    if campaign == "extended":
        representative_ids = {
            "valid_limit_b32",
            "account_budget_b32",
            "token_bundle_b32_d16",
        }
        focused_legacy = [
            row for row in core if row.composition_id in representative_ids
        ]
        return focused_legacy + linked
    return core + linked


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


def input_path(project_root: Path, experiment_name: str) -> Path:
    return project_root / "inputs" / "valid" / f"{experiment_name}.json"
