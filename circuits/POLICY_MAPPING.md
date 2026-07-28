# Circuit-to-policy mapping

The circuits implement representative policy kernels, not complete payment
protocols. Hidden values must be bound to authenticated transaction objects or
state in a complete system.

## Individual policy kernels

| Policy | Canonical wrappers | Public inputs | Private inputs | In-proof predicate |
|---|---|---|---|---|
| `pi_valid` | `local_financial_validity_{16,32,64}.circom` | none | `balance`, `amount` | `0 < amount <= balance` |
| `pi_limit` | `operating_limit_{16,32,64}.circom` | `window_limit` | `spent_window`, `amount` | `spent_window + amount <= window_limit` |
| `pi_budget` | `privacy_budget_{16,32,64}.circom` | `anonymity_budget` | `spent_private`, `amount` | `spent_private + amount <= anonymity_budget` |
| `pi_trans` | `state_transition_and_conservation_{16,32,64}.circom` | none | balances, new balances, amount | correct updates and value conservation |
| `pi_mem` | `merkle_membership_depth_{8,16,32}.circom` | `root` | leaf, path elements, path indices | Poseidon Merkle membership |
| `pi_null` | `nullifier_correctness_poseidon.circom` | `nullifier`, `nullifier_domain` | `asset_secret` | correct nullifier derivation |

The `nullifier_correctness_poseidon.circom` filename is retained for
compatibility. The circuit proves derivation only; the ledger must reject a
nullifier that has already appeared.

## Composed policies

| Wrapper | Policy conjunction |
|---|---|
| `local_validity_and_operating_limit_{16,32,64}.circom` | `pi_valid AND pi_limit` |
| `account_policy_core_{16,32,64}.circom` | `pi_valid AND pi_trans AND pi_limit` |
| `account_policy_with_privacy_budget_{16,32,64}.circom` | `pi_valid AND pi_trans AND pi_limit AND pi_budget` |
| `token_policy_bundle_32_depth_{8,16,32}.circom` | `pi_mem AND pi_null AND pi_valid AND pi_budget` |

## Commitment-linked composition

The `linked_*` circuits bind their policy inputs to a common Poseidon-based
transaction commitment. The public signal is named `tx_tag` for compatibility;
the paper and generated tables use the term **transaction commitment**.

## Deliberately excluded policy families

- `pi_auth`: authorization and eligibility;
- `pi_audit`: audit, disclosure, and tracing;
- `pi_struct`: privacy structure and unlinkability.

Their costs depend on the selected credential, encryption/tracing, or
shuffle/permutation construction and are therefore not represented by one
generic circuit.
