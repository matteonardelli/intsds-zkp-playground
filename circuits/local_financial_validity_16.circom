pragma circom 2.1.6;

include "templates/payment_policy_model.circom";

/* pi_valid; balance and amount are private. */
component main = LocalFinancialValidity(16);
