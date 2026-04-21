pragma circom 2.1.6;

include "circomlib/circuits/comparators.circom";

/*
  Proves both:
    1) balance >= amount
    2) spent_window + amount <= limit

  Private inputs:
    - balance
    - spent_window
  Public inputs:
    - amount
    - limit

  Rationale:
    Minimal realistic composition of a financial correctness constraint
    and a regulatory policy constraint.
*/

template BalanceAndLimit(nBits) {
    signal input balance;      // private
    signal input spent_window; // private
    signal input amount;       // public
    signal input limit;        // public

    signal total_spent;

    total_spent <== spent_window + amount;

    component enoughBalance = GreaterEqThan(nBits);
    enoughBalance.in[0] <== balance;
    enoughBalance.in[1] <== amount;

    component withinLimit = GreaterEqThan(nBits);
    withinLimit.in[0] <== limit;
    withinLimit.in[1] <== total_spent;

    enoughBalance.out === 1;
    withinLimit.out === 1;
}

component main {public [amount, limit]} = BalanceAndLimit(32);