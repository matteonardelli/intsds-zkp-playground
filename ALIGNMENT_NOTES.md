# Alignment notes

This revision aligns the Circom source tree with `sec_policymodel.tex`.

## Main changes

1. Added canonical circuits for `pi_valid`, `pi_limit`, `pi_budget`,
   `pi_trans`, and `pi_mem`.
2. Added account-style and token-style policy compositions.
3. Made transaction amounts private in canonical wrappers.
4. Added explicit unsigned range constraints and `(nBits + 1)`-bit cumulative
   intermediates.
5. Clarified that nullifier correctness and ledger-level non-spentness are
   distinct checks.
6. Retained the original circuit names as compatibility aliases for the current
   preliminary benchmark script.
7. Did not create generic circuits for `pi_auth`, `pi_audit`, or `pi_struct`,
   because the policy-model section explicitly treats them as protocol-specific
   and outside the initial experimental scope.

## Deferred work

The current `scripts/run_bench.py`, plotting script, and table builder remain
preliminary. The next step is to define an evaluation manifest and input
generators, especially for Poseidon Merkle trees and token-policy bundles.
