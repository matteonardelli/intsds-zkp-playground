# ZKP Policy Kernels for Privacy-Preserving Payments

This repository contains Circom circuits aligned with the policy model used in
the paper on ZKP-based policy enforcement for privacy-preserving payment
systems.

The code does **not** implement a complete payment system. It isolates the
constraint-enforcement layer so that the cost of representative policy classes
can later be evaluated individually and in composition.

## Policy-model coverage

The canonical circuits cover the policy classes selected for experimental
analysis:

- **Local financial validity** (`pi_valid`)
- **Operating/regulatory limits** (`pi_limit`)
- **Privacy/anonymity budgets** (`pi_budget`)
- **State transition and value conservation** (`pi_trans`)
- **Membership and nullifier correctness** (`pi_mem`)

The paper also models authorization/eligibility, audit/disclosure/tracing, and
privacy-structure/unlinkability policies. These are deliberately not reduced to
one generic circuit because their implementation is strongly protocol-specific.

See [`circuits/POLICY_MAPPING.md`](circuits/POLICY_MAPPING.md) for the exact
mapping between policy predicates, wrappers, and public/private inputs.

## Canonical circuit families

### Individual policy classes

```text
circuits/local_financial_validity_{16,32,64}.circom
circuits/operating_limit_{16,32,64}.circom
circuits/privacy_budget_{16,32,64}.circom
circuits/state_transition_and_conservation_{16,32,64}.circom
circuits/merkle_membership_depth_{8,16,32}.circom
circuits/nullifier_correctness_poseidon.circom
```

### Policy composition

```text
circuits/local_validity_and_operating_limit_{16,32,64}.circom
circuits/account_policy_core_{16,32,64}.circom
circuits/account_policy_with_privacy_budget_{16,32,64}.circom
circuits/token_policy_bundle_32_depth_{8,16,32}.circom
```

All templates are defined in:

```text
circuits/templates/payment_policy_model.circom
```

## Design decisions

### Private transaction values

The canonical wrappers keep the transaction amount and financial state private.
Only policy thresholds, Merkle roots, and nullifiers are public where required.
This better matches the privacy-preserving setting described in the paper.

These circuits are policy kernels. In a complete protocol, hidden amounts and
balances must also be bound to transaction commitments, ciphertexts, account
state, or token commitments. The benchmark intentionally isolates the policy
predicate rather than reproducing the full protocol stack.

### Unsigned-integer semantics

Every financial value is explicitly range-constrained. Cumulative additions use
an `(nBits + 1)`-bit intermediate, preventing overflow from changing the
intended semantics inside the SNARK field.

### Nullifiers

The nullifier circuit proves correct derivation from a hidden asset secret. It
does not prove global non-spentness by itself. A ledger or state-transition
layer must reject a public nullifier that has already appeared.

### Operating limits vs. anonymity budgets

These classes are semantically different but can compile to the same arithmetic
shape. Keeping both circuits supports the paper's distinction between policy
semantics and low-level cost drivers.

## Compatibility with the existing scripts

The original circuit names are retained as compatibility wrappers:

```text
sufficient_balance_*
cumulative_limit_*
balance_and_limit_*
balance_limit_and_conservation_*
```

They now route to the policy-model-aligned templates, so the existing benchmark
script can still be used for preliminary checks. New evaluation scripts should
use the canonical names and will be defined separately.

## Requirements

- Python 3.9+
- Node.js
- Circom 2.1.6 or compatible
- SnarkJS
- `circomlib`

Install the JavaScript dependency from the repository root:

```bash
npm install
```

The existing scripts expect the Powers of Tau file at:

```text
powersOfTau28_hez_final_12.ptau
```

## Experimental scripts

The scripts under `scripts/` implement the first policy-model campaign,
including the 28 monolithic circuit configurations, sequential separate-proof
baselines, deterministic Poseidon/Merkle inputs, raw per-run collection,
summary statistics, figures, and IEEE-compatible LaTeX tables. See
[`scripts/README.md`](scripts/README.md) for the workflow.
