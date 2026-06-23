pragma circom 2.1.6;

include "templates/payment_policy_model.circom";

/* pi_mem/non-spentness support; ledger-level non-reuse is external. */
component main {public [nullifier, nullifier_domain]} = NullifierCorrectness();
