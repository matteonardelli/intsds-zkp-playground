pragma circom 2.1.6;

include "templates/balance_limit_and_conservation.circom";

component main {public [amount, limit]} = BalanceLimitAndConservation(16);