# Model and implementation alignment

The source tree aligns the benchmark with the policy model used in the paper.

- `pi_valid`, `pi_limit`, `pi_budget`, and `pi_trans` are arithmetic kernels.
- `pi_mem` is authenticated-set membership.
- `pi_null` is correct nullifier derivation; global non-reuse remains external.
- Token bundles include both `pi_mem` and `pi_null`.
- Financial values are explicitly range-constrained, and cumulative additions
  use an `(nBits + 1)`-bit intermediate.
- Commitment-linked components expose the same Poseidon-based transaction
  commitment through the historical `tx_tag` signal.
- Authorization, audit/disclosure, and privacy-structure policies remain out of
  scope because their circuit costs are construction-specific.

Compatibility wrappers and historical filenames are retained to preserve old
result fingerprints and input files. Paper-facing labels are normalized by the
post-processing scripts.
