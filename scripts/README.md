# Experimental campaign scripts

The complete experimental matrix is defined only in:

```text
scripts/experiment_manifest.py
```

`run_bench.py`, `validate_circuits.py`, and `summarize_results.py` all import
this manifest. There is no separate runner or manifest for the linked
extension.

## Campaign profiles

- `core`: original individual kernels, monolithic compositions, and unbound
  separate-proof lower bounds;
- `extended`: the focused RQ3 campaign, rerunning the three representative
  legacy variants together with their transaction-tag-linked counterparts;
- `paper`: the complete core matrix plus the linked extension.

## Install

From the repository root:

```bash
npm install
```

Place the only supported Powers of Tau file at:

```text
powersOfTau28_hez_final_15.ptau
```

The post-processing scripts use only the Python standard library. Plot and
LaTeX-table generation additionally require `pandas` and `matplotlib`.

## Generate deterministic inputs

```bash
node scripts/generate_inputs.js
```

The same generator creates inputs for every campaign profile. The runner calls
it automatically when required inputs are missing.

## Functional validation

```bash
python3 scripts/validate_circuits.py --campaign extended
python3 scripts/validate_circuits.py --campaign paper
```

The extended validation checks invalid tags, binding-only field mutations, and
application-level tag equality across component proofs.

## Intern: extended campaign only

Smoke test:

```bash
python3 scripts/run_bench.py \
  --campaign extended \
  --repeats 3 \
  --warmups 1 \
  --blocks 1 \
  --force-rebuild
```

Full extended campaign:

```bash
python3 scripts/run_bench.py \
  --campaign extended \
  --repeats 30 \
  --warmups 5 \
  --blocks 3
```

## Complete paper campaign

```bash
python3 scripts/run_bench.py --campaign paper
```

Defaults are Groth16, five shuffled warm-ups, 30 measured repetitions, three
blocks, and deterministic seed `20260623`.

Results are stored under:

```text
results/<UTC-run-id>_<campaign>_<proving-system>/
```

## Summaries

```bash
python3 scripts/summarize_results.py results/<run-id>
```

The summarizer writes:

- `summary.csv`;
- `composition_comparison.csv`, distinguishing `legacy` and `linked` pairs;
- `binding_overhead.csv`;
- `composition_variants.csv`;
- `limit_budget_equivalence.csv`.

The `legacy` separate rows are optimistic unbound lower bounds. The `linked`
rows are the security-consistent RQ3 comparison.
