pragma circom 2.1.6;
include "payment_policy_model.circom";

/* Deprecated compatibility alias for pi_valid. */
template SufficientBalance(nBits) {
    signal input balance;
    signal input amount;

    component policy = LocalFinancialValidity(nBits);
    policy.balance <== balance;
    policy.amount <== amount;
}
