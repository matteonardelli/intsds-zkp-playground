pragma circom 2.1.6;

include "templates/payment_policy_model.circom";

/* pi_mem; leaf and authentication path are private. */
component main {public [root]} = MerkleMembership(16);
