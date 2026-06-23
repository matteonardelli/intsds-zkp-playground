# Experimental campaign scripts

This directory implements the first experimental matrix associated with the
paper's policy model.

## Matrix

The campaign includes 28 monolithic circuit configurations:

- individual arithmetic policies at 16, 32, and 64 bits;
- Merkle membership at depths 8, 16, and 32;
- Poseidon nullifier correctness;
- three account-policy compositions at 16, 32, and 64 bits;
- a token-policy bundle at 32 bits and Merkle depths 8, 16, and 32.

It also executes 12 logical separate-proof baselines for the composed policies.
The single source of truth is `experiment_manifest.py`.

## Install

From the repository root:

```bash
npm install
```

Place the Powers of Tau file at:

```text
powersOfTau28_hez_final_12.ptau
```

The Python post-processing scripts additionally require:

```bash
python -m pip install pandas matplotlib
```

## Generate deterministic inputs

```bash
node scripts/generate_inputs.js
```

The runner invokes this command automatically if input files are missing.
Large integers are stored as decimal strings.

## Functional validation

Before timing, run valid, boundary, and invalid witness checks:

```bash
python scripts/validate_circuits.py
```

The report is written to `results/functional_validation.csv`. Invalid cases
are expected to fail witness generation and are not part of the performance
dataset.

## Smoke test

```bash
python scripts/run_bench.py \
  --repeats 3 --warmups 1 --blocks 1 \
  --families local_financial_validity \
  --no-separate
```

## First full campaign

```bash
python scripts/run_bench.py
```

Defaults:

- Groth16;
- 5 shuffled warm-up rounds;
- 30 measured repetitions per logical configuration;
- 3 blocks of 10 repetitions;
- monolithic and sequential separate-proof executions;
- deterministic seed `20260623`.

Results are stored under:

```text
results/<UTC-run-id>_groth16/
```

The runner writes:

- `environment.json`: hardware/software/provenance metadata;
- `artifacts.csv`: static circuit metrics and offline compile/setup costs;
- `raw_runs.csv`: one row per logical measured execution;
- `component_runs.csv`: one row per component proof, including components of
  separate-proof baselines.

## Summaries, plots, and tables

```bash
python scripts/summarize_results.py results/<run-id>
python scripts/plot_results.py results/<run-id>
python scripts/build_tables.py results/<run-id>
```

The summarizer creates:

- `summary.csv`;
- `composition_comparison.csv`;
- `limit_budget_equivalence.csv`.

The plotting script creates independent PDF figures under `figures/`. The table
script creates IEEE-compatible LaTeX fragments under `tables/`.

## Methodological notes

Compilation and trusted setup are treated as offline costs and are not included
in witness/prove/verify timings. Source-fingerprinted build directories prevent
stale R1CS and proving-key reuse after circuit changes.

The nullifier circuit proves correct derivation only. Ledger-level nullifier
non-reuse remains an external state check.
