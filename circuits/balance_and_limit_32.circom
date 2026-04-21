pragma circom 2.1.6;

include "templates/balance_and_limit.circom";

component main {public [amount, limit]} = BalanceAndLimit(32);