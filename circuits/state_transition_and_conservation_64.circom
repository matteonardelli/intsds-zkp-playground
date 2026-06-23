pragma circom 2.1.6;

include "templates/payment_policy_model.circom";

/* pi_trans; pre-state, post-state, and amount are private policy-kernel inputs. */
component main = StateTransitionAndConservation(64);
