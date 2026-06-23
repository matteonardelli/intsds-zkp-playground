# Circuit-to-policy mapping

The circuits in this directory implement the experimentally scoped classes in
`sec_policymodel.tex`. They are **policy kernels**, not complete payment
protocols. Private values must be bound to commitments, ciphertexts, or
protocol state in a full implementation.

## Canonical primitive-policy families

| Policy-model class | Canonical wrappers | Public inputs | Private inputs | Predicate represented |
|---|---|---|---|---|
| `pi_valid` | `local_financial_validity_{16,32,64}.circom` | none | `balance`, `amount` | `0 < amount <= balance` |
| `pi_limit` | `operating_limit_{16,32,64}.circom` | `window_limit` | `spent_window`, `amount` | `spent_window + amount <= window_limit` |
| `pi_budget` | `privacy_budget_{16,32,64}.circom` | `anonymity_budget` | `spent_private`, `amount` | `spent_private + amount <= anonymity_budget` |
| `pi_trans` | `state_transition_and_conservation_{16,32,64}.circom` | none | balances, new balances, amount | correct sender/receiver updates and value conservation |
| `pi_mem` | `merkle_membership_depth_{8,16,32}.circom` | `root` | leaf, path elements, path indices | Poseidon Merkle membership |
| `pi_mem` support | `nullifier_correctness_poseidon.circom` | `nullifier`, `nullifier_domain` | `asset_secret` | correct nullifier derivation |

`NullifierCorrectness` does not prove that the nullifier is globally unused.
The ledger or state-transition layer must reject repeated public nullifiers.

## Composed-policy families

| Wrapper | Policy conjunction |
|---|---|
| `local_validity_and_operating_limit_{16,32,64}.circom` | `pi_valid AND pi_limit` |
| `account_policy_core_{16,32,64}.circom` | `pi_valid AND pi_trans AND pi_limit` |
| `account_policy_with_privacy_budget_{16,32,64}.circom` | `pi_valid AND pi_trans AND pi_limit AND pi_budget` |
| `token_policy_bundle_32_depth_{8,16,32}.circom` | `pi_mem AND pi_valid AND pi_budget`, plus nullifier correctness |

## Deliberately excluded classes

The following classes remain part of the paper model but are not represented
by generic benchmark circuits:

- `pi_auth`: authorization and eligibility;
- `pi_audit`: audit, disclosure, and tracing;
- `pi_struct`: privacy structure and unlinkability.

Their implementation depends strongly on the credential scheme, encryption or
tracing construction, and shuffle/permutation proof system. Reducing them to a
single generic Circom circuit would overstate comparability across systems.

## Compatibility wrappers

The original wrappers (`sufficient_balance_*`, `cumulative_limit_*`,
`balance_and_limit_*`, and `balance_limit_and_conservation_*`) are retained so
that the existing benchmark script still compiles. They now route to the
policy-model-aligned templates. New evaluation scripts should use the canonical
names above.
