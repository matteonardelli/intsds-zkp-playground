# First experimental campaign

This revision aligns the evaluation tooling with `sec_policymodel.tex`.

## Included configurations

- 28 monolithic circuit configurations;
- 12 sequential separate-proof baselines;
- 5 warm-ups and 30 measured repetitions by default;
- 3 shuffled measurement blocks;
- Groth16 as the default first-campaign backend.

## New scripts

- `experiment_manifest.py`: the experimental matrix and baseline mapping;
- `generate_inputs.js`: deterministic arithmetic, Poseidon, Merkle, and
  nullifier input generation;
- `validate_circuits.py`: valid/boundary/invalid witness tests;
- `run_bench.py`: fingerprinted compile/setup, shuffled runs, raw collection,
  and separate-proof execution;
- `summarize_results.py`: distribution statistics and composition ratios;
- `plot_results.py`: RQ-oriented PDF plots;
- `build_tables.py`: IEEE-compatible LaTeX result tables.

## Paper source

`paper/sec_evaluation.tex` defines RQ1--RQ4, the experimental matrix,
methodology, metrics, result placeholders, discussion prompts, and threats to
validity. It expects generated artifacts under `results/latest`; the runner
updates that symlink after a completed campaign when supported by the OS.

## Not executed in this environment

The complete cryptographic campaign was not executed here because Circom,
SnarkJS, the Powers of Tau file, and installed Node dependencies are required.
Python syntax, JavaScript syntax, post-processing over a synthetic dataset, and
LaTeX compilation of the evaluation section were validated.
