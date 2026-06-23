pragma circom 2.1.6;
include "payment_policy_model.circom";

/* Deprecated compatibility alias for pi_valid AND pi_limit. */
template BalanceAndLimit(nBits) {
    signal input balance;
    signal input spent_window;
    signal input amount;
    signal input limit;

    component policy = LocalValidityAndOperatingLimit(nBits);
    policy.balance <== balance;
    policy.spent_window <== spent_window;
    policy.amount <== amount;
    policy.window_limit <== limit;
}
