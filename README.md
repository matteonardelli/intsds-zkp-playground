# ZKP Policy Kernels for Privacy-Preserving Payments

This repository contains the Circom circuits and reproducibility scripts used
to model and evaluate recurring zero-knowledge policies for privacy-preserving
payments.

The code does **not** implement a complete payment system. It isolates the
policy-enforcement layer so that representative relations can be evaluated
individually and in composition under a fixed Circom/Groth16/SnarkJS toolchain.

## Policy coverage

The benchmark distinguishes the following in-proof policies:

- local financial validity (`pi_valid`);
- operating or regulatory limits (`pi_limit`);
- privacy or anonymity budgets (`pi_budget`);
- state transition and value conservation (`pi_trans`);
- authenticated-set membership (`pi_mem`);
- nullifier derivation (`pi_null`).

Membership and nullifier derivation belong to the same broader asset/state
policy family in the paper, but they are separate policy kernels and are
measured separately. Global nullifier non-reuse remains a ledger-level check.

Authorization, audit/disclosure/tracing, and privacy-structure policies are
part of the model but are not represented by one generic benchmark circuit,
because their costs depend strongly on the selected credential, encryption,
tracing, or shuffle construction.

See [`circuits/POLICY_MAPPING.md`](circuits/POLICY_MAPPING.md) for the mapping
between policies, wrappers, and public/private inputs.

## Circuit families

### Individual kernels

```text
circuits/local_financial_validity_{16,32,64}.circom
circuits/operating_limit_{16,32,64}.circom
circuits/privacy_budget_{16,32,64}.circom
circuits/state_transition_and_conservation_{16,32,64}.circom
circuits/merkle_membership_depth_{8,16,32}.circom
circuits/nullifier_correctness_poseidon.circom
```

The last filename is retained for compatibility; the paper-facing policy name
is **nullifier derivation** (`pi_null`).

### Policy compositions

```text
circuits/local_validity_and_operating_limit_{16,32,64}.circom
circuits/account_policy_core_{16,32,64}.circom
circuits/account_policy_with_privacy_budget_{16,32,64}.circom
circuits/token_policy_bundle_32_depth_{8,16,32}.circom
```

The commitment-linked RQ3 circuits retain the historical `linked_*` filenames.
Their public `tx_tag` signal is the implementation of the common Poseidon-based
transaction commitment described in the paper.

## Requirements

- Python 3.9+
- Node.js 20 or compatible
- Circom 2.2.x
- SnarkJS 0.7.x
- `circomlib` 2.0.5
- `circomlibjs`
- `pandas` and `matplotlib` for paper artifacts

Install dependencies:

```bash
npm install
python3 -m pip install -r requirements.txt
```

Place the supported Powers of Tau file in the repository root:

```text
powersOfTau28_hez_final_15.ptau
```

Large `.ptau`, `.zkey`, witness, build, and result files are intentionally not
tracked by Git.

## Reproduce the paper evaluation

The canonical entry point is one command:

```bash
python3 scripts/reproduce_paper.py
```

Equivalently:

```bash
make reproduce-paper
```

The command performs functional validation, runs every configuration used by
RQ1, RQ2, and RQ3, computes the derived statistics, and generates the LaTeX
tables and figures. All outputs are written under one timestamped directory:

```text
results/<run-id>/
├── environment.json
├── artifacts.csv
├── raw_runs.csv
├── component_runs.csv
├── functional_validation.csv
├── summary.csv
├── composition_variants.csv
├── composition_comparison.csv
├── binding_overhead.csv
├── limit_budget_equivalence.csv
├── reproduction.json
├── tables/
└── figures/
```

Default settings are five shuffled warm-ups, 30 measured repetitions, three
blocks, deterministic seed `20260623`, and Groth16. A small end-to-end smoke
test is:

```bash
python3 scripts/reproduce_paper.py \
  --repeats 3 --warmups 1 --blocks 1
```

Partial scopes are available only for development or targeted reruns:

```bash
python3 scripts/run_bench.py --scope rq1-rq2
python3 scripts/run_bench.py --scope rq3
```

They are subsets of the same evaluation design, not separate scientific
campaigns. Technical comparison groups such as `baseline` and
`commitment_linked` identify RQ3 variants within a run; they do not identify
separate runs.

## Rebuild artifacts from an existing run

A complete run can be post-processed again with:

```bash
python3 scripts/build_paper_artifacts.py results/<run-id>
```

By default, the tables and figures are written into that same result directory.
The optional `--rq3-run` argument exists only to recover older archived data in
which RQ1/RQ2 and RQ3 were stored separately; new reproductions should not use
it.

See [`scripts/README.md`](scripts/README.md) for the output schema and metric
definitions.

## Validation and tests

Static Python tests:

```bash
python3 -m unittest discover -s tests
```

Circuit-level functional validation requires Circom, Node.js, and the installed
npm dependencies. The complete proof benchmark additionally requires SnarkJS
and the Powers of Tau file.
