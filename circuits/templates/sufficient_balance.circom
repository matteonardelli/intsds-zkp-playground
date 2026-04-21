pragma circom 2.1.6;

include "circomlib/circuits/comparators.circom";

/*
  Proves that balance >= amount.

  Private inputs:
    - balance
  Public inputs:
    - amount

  Rationale:
    Representative of a local correctness constraint in account-based systems.
*/

template SufficientBalance(nBits) {
    signal input balance;   // private
    signal input amount;    // public

    component geq = GreaterEqThan(nBits);
    geq.in[0] <== balance;
    geq.in[1] <== amount;

    geq.out === 1;
}
