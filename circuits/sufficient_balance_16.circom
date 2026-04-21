pragma circom 2.1.6;

include "templates/sufficient_balance.circom";

component main {public [amount]} = SufficientBalance(16);