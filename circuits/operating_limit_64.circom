pragma circom 2.1.6;

include "templates/payment_policy_model.circom";

/* pi_limit; cumulative state and amount are private, threshold is public. */
component main {public [window_limit]} = OperatingLimit(64);
