pragma circom 2.1.6;

include "circomlib/circuits/comparators.circom";

/*
  Proves that spent_window + amount <= limit.

  Private inputs:
    - spent_window
  Public inputs:
    - amount
    - limit

  Rationale:
    Representative of cumulative regulatory constraints,
    e.g., daily limits or anonymity budgets.
*/

template CumulativeLimit(nBits) {
    signal input spent_window; // private
    signal input amount;       // public
    signal input limit;        // public

    signal total_spent;

    total_spent <== spent_window + amount;

    component geq = GreaterEqThan(nBits);
    geq.in[0] <== limit;
    geq.in[1] <== total_spent;

    geq.out === 1;
}

component main {public [amount, limit]} = CumulativeLimit(32);