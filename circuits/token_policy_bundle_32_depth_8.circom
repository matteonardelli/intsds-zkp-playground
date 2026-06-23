pragma circom 2.1.6;

include "templates/payment_policy_model.circom";

/* pi_mem AND pi_valid AND pi_budget plus public-nullifier correctness. */
component main {public [root, nullifier, nullifier_domain, anonymity_budget]} = TokenPolicyBundle(32, 8);
