pragma circom 2.1.6;

include "circomlib/circuits/comparators.circom";

/*
  Proves:
    1) sender_balance >= amount
    2) spent_window + amount <= limit
    3) sender_new = sender_balance - amount
    4) receiver_new = receiver_balance + amount
    5) value conservation:
         sender_balance + receiver_balance
         =
         sender_new + receiver_new

  Private inputs:
    - sender_balance
    - receiver_balance
    - spent_window
    - sender_new
    - receiver_new
  Public inputs:
    - amount
    - limit

  Rationale:
    More realistic transaction core for account-based private payments.
*/

template BalanceLimitAndConservation(nBits) {
    signal input sender_balance;   // private
    signal input receiver_balance; // private
    signal input spent_window;     // private

    signal input sender_new;       // private
    signal input receiver_new;     // private

    signal input amount;           // public
    signal input limit;            // public

    signal total_spent;
    signal total_before;
    signal total_after;

    // Regulatory cumulative constraint
    total_spent <== spent_window + amount;

    component enoughBalance = GreaterEqThan(nBits);
    enoughBalance.in[0] <== sender_balance;
    enoughBalance.in[1] <== amount;

    component withinLimit = GreaterEqThan(nBits);
    withinLimit.in[0] <== limit;
    withinLimit.in[1] <== total_spent;

    enoughBalance.out === 1;
    withinLimit.out === 1;

    // State updates
    sender_new === sender_balance - amount;
    receiver_new === receiver_balance + amount;

    // Conservation of value
    total_before <== sender_balance + receiver_balance;
    total_after <== sender_new + receiver_new;
    total_before === total_after;
}

component main {public [amount, limit]} = BalanceLimitAndConservation(32);