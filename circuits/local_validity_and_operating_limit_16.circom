pragma circom 2.1.6;

include "templates/payment_policy_model.circom";

/* pi_valid AND pi_limit; amount remains private. */
component main {public [window_limit]} = LocalValidityAndOperatingLimit(16);
