pragma circom 2.1.6;

include "templates/cumulative_limit.circom";

component main {public [amount, limit]} = CumulativeLimit(64);