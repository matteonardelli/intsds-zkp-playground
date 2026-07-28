# Experimental scripts

The complete experimental matrix is defined once in:

```text
scripts/experiment_manifest.py
```

The runner, validator, summarizer, table builder, and plotting scripts consume
this shared definition.

## Canonical one-command reproduction

```bash
python3 scripts/reproduce_paper.py
```

This command:

1. validates all circuits and binding checks;
2. runs all configurations used by RQ1, RQ2, and RQ3;
3. writes raw logical and component measurements;
4. computes distribution summaries and RQ3 ratios;
5. generates all LaTeX tables and figures.

Everything is stored in one directory, `results/<run-id>/`. The default run
contains five warm-ups and 30 measured repetitions per logical configuration,
divided into three shuffled blocks.

A smoke test is:

```bash
python3 scripts/reproduce_paper.py \
  --repeats 3 --warmups 1 --blocks 1
```

## Optional research-question scopes

The low-level runner supports two partial scopes for development:

```bash
python3 scripts/run_bench.py --scope rq1-rq2
python3 scripts/run_bench.py --scope rq3
```

The default `--scope all` runs the complete paper evaluation. Partial scopes do
not define different methodologies or campaigns.

Within RQ3, `baseline` and `commitment_linked` are comparison groups in the
same run:

- baseline monolithic circuit with a shared witness;
- unbound separate-proof computational baseline;
- commitment-linked monolithic circuit;
- commitment-linked separate proofs.

The implementation signal `tx_tag` is normalized to
`transaction_commitment` in derived CSV files.

## Result files

Raw and structural files:

- `environment.json`;
- `artifacts.csv`;
- `raw_runs.csv`;
- `component_runs.csv`;
- `functional_validation.csv`.

Derived files:

- `summary.csv`;
- `composition_variants.csv`;
- `composition_comparison.csv`;
- `binding_overhead.csv`;
- `limit_budget_equivalence.csv`.

Paper tables:

```text
tables/table_representative_costs.tex
tables/table_composition_ratios.tex
tables/table_binding_overhead.tex
```

Paper figures:

```text
figures/fig_constraints_bitwidth.pdf
figures/fig_proving_distribution_32.pdf
figures/fig_merkle_constraints.pdf
figures/fig_merkle_proving_distribution.pdf
figures/fig_composition_proving_ratio.pdf
```

## Metrics

For each measured repetition, the harness records:

- witness-generation time;
- proving time;
- verification time;
- bundle-level commitment-equality-check time;
- total online time;
- serialized proof size;
- serialized public-output size;
- verification and binding outcomes.

Static metadata include constraint and wire counts, public/private inputs,
R1CS and WASM sizes, and proving- and verification-key sizes. Compilation and
circuit-specific setup are performed before online timing.

## Rebuilding tables and figures

For any complete result directory:

```bash
python3 scripts/build_paper_artifacts.py results/<run-id>
```

The output defaults to the same directory. The command expects all RQ1--RQ3
measurements and derived CSV files to belong to that single evaluation run.
