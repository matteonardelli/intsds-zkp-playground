pragma circom 2.1.6;

include "templates/payment_policy_model.circom";

/* pi_valid AND pi_trans AND pi_limit. */
component main {public [window_limit]} = AccountPolicyCore(64);
