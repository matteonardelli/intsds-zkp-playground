# Unified experimental campaign

The repository uses a single experimental matrix:

```text
scripts/experiment_manifest.py
```

All runners, validators, and summarizers import this manifest. There is no
separate linked-campaign manifest or runner.

## Campaign profiles

- `core`: individual policy kernels, original monolithic compositions, and the
  original unbound separate-proof lower bounds.
- `extended`: the focused RQ3 campaign. It reruns the three representative
  legacy monolithic/unbound-separate variants together with their linked
  monolithic/linked-separate counterparts, so all four variants are measured
  in the same shuffled run.
- `paper`: the union of the complete `core` matrix and the linked extension; this is the complete
  reproducibility campaign.

The only supported Powers of Tau file is expected in the repository root:

```text
powersOfTau28_hez_final_15.ptau
```

## Intern: run the focused extended campaign

Install dependencies and generate all deterministic inputs:

```bash
npm install
node scripts/generate_inputs.js
```

Run functional checks:

```bash
python3 scripts/validate_circuits.py --campaign extended
```

Run a smoke test:

```bash
python3 scripts/run_bench.py \
  --campaign extended \
  --repeats 3 \
  --warmups 1 \
  --blocks 1 \
  --force-rebuild
```

Run the full extension:

```bash
python3 scripts/run_bench.py \
  --campaign extended \
  --repeats 30 \
  --warmups 5 \
  --blocks 3
```

Summarize the generated result directory:

```bash
python3 scripts/summarize_results.py results/<run-id>
```

The extended campaign contains 12 logical configurations, 22 unique circuits,
360 measured logical observations, and 780 measured component observations. It
produces same-run comparisons among legacy monolithic, unbound separate, linked
monolithic, and linked separate variants.

## Reproduce the complete paper

```bash
python3 scripts/validate_circuits.py --campaign paper
python3 scripts/run_bench.py --campaign paper
python3 scripts/summarize_results.py results/<run-id>
```

The summary command generates:

- `summary.csv`;
- `composition_comparison.csv`, with separate `legacy` and `linked` comparison-group rows;
- `binding_overhead.csv`, comparing linked and legacy variants;
- `composition_variants.csv`;
- `limit_budget_equivalence.csv`.

## Interpretation

The `legacy` separate-proof rows are retained as optimistic unbound lower
bounds. The `linked` comparison is the security-consistent RQ3 experiment:
all component proofs recompute a public Poseidon `tx_tag`, and the harness
accepts the bundle only if every proof verifies and all tags coincide.
