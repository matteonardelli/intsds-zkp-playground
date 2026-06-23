pragma circom 2.1.6;
include "payment_policy_model.circom";

/* Deprecated compatibility alias for pi_valid AND pi_trans AND pi_limit. */
template BalanceLimitAndConservation(nBits) {
    signal input sender_balance;
    signal input receiver_balance;
    signal input spent_window;
    signal input sender_new;
    signal input receiver_new;
    signal input amount;
    signal input limit;

    component policy = AccountPolicyCore(nBits);
    policy.sender_balance <== sender_balance;
    policy.receiver_balance <== receiver_balance;
    policy.spent_window <== spent_window;
    policy.amount <== amount;
    policy.sender_new <== sender_new;
    policy.receiver_new <== receiver_new;
    policy.window_limit <== limit;
}
