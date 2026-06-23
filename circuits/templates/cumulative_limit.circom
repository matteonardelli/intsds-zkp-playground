pragma circom 2.1.6;
include "payment_policy_model.circom";

/* Deprecated compatibility alias for pi_limit. */
template CumulativeLimit(nBits) {
    signal input spent_window;
    signal input amount;
    signal input limit;

    component policy = OperatingLimit(nBits);
    policy.spent_window <== spent_window;
    policy.amount <== amount;
    policy.window_limit <== limit;
}
