pragma circom 2.1.6;

include "templates/linked_policy_composition.circom";

component main {public [tx_tag, root, nullifier, nullifier_domain, anonymity_budget]} = LinkedTokenBundleMonolithic(32, 16);
