pragma circom 2.1.6;

include "templates/linked_policy_composition.circom";

component main {public [tx_tag, window_limit]} = LinkedValidLimitValidity(32);
