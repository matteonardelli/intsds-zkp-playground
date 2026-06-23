pragma circom 2.1.6;

include "templates/payment_policy_model.circom";

/* pi_budget; private-mode spending and amount are private, budget is public. */
component main {public [anonymity_budget]} = PrivacyBudget(16);
