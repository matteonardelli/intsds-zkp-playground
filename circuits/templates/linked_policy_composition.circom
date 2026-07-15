pragma circom 2.1.6;

include "payment_policy_model.circom";

/*
 * Security-consistent composition benchmarks.
 *
 * Each proof exposes a public transaction-binding tag.  The tag is a
 * domain-separated Poseidon hash over all hidden transaction fields shared by
 * the policy bundle, the relevant public context, and private blinding
 * randomness.  Monolithic circuits compute the tag once; every separate proof
 * recomputes it.  A verifier accepts a separate-proof bundle only when all
 * component proofs verify and expose the same tag.
 *
 * These circuits are benchmark constructions, not complete payment protocols.
 */

/* ------------------------------------------------------------------------- */
/* Validity + operating-limit bundle                                          */
/* ------------------------------------------------------------------------- */

template ValidLimitBinding() {
    signal input balance;
    signal input spent_window;
    signal input amount;
    signal input window_limit;
    signal input binding_randomness;
    signal input tx_tag;

    component h = Poseidon(6);
    h.inputs[0] <== 1101;
    h.inputs[1] <== balance;
    h.inputs[2] <== spent_window;
    h.inputs[3] <== amount;
    h.inputs[4] <== window_limit;
    h.inputs[5] <== binding_randomness;
    h.out === tx_tag;
}

template LinkedValidLimitMonolithic(nBits) {
    signal input balance;
    signal input spent_window;
    signal input amount;
    signal input window_limit;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = ValidLimitBinding();
    binding.balance <== balance;
    binding.spent_window <== spent_window;
    binding.amount <== amount;
    binding.window_limit <== window_limit;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = LocalValidityAndOperatingLimit(nBits);
    policy.balance <== balance;
    policy.spent_window <== spent_window;
    policy.amount <== amount;
    policy.window_limit <== window_limit;
}

template LinkedValidLimitValidity(nBits) {
    signal input balance;
    signal input spent_window;
    signal input amount;
    signal input window_limit;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = ValidLimitBinding();
    binding.balance <== balance;
    binding.spent_window <== spent_window;
    binding.amount <== amount;
    binding.window_limit <== window_limit;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = LocalFinancialValidity(nBits);
    policy.balance <== balance;
    policy.amount <== amount;
}

template LinkedValidLimitLimit(nBits) {
    signal input balance;
    signal input spent_window;
    signal input amount;
    signal input window_limit;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = ValidLimitBinding();
    binding.balance <== balance;
    binding.spent_window <== spent_window;
    binding.amount <== amount;
    binding.window_limit <== window_limit;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = OperatingLimit(nBits);
    policy.spent_window <== spent_window;
    policy.amount <== amount;
    policy.window_limit <== window_limit;
}

/* ------------------------------------------------------------------------- */
/* Account core + privacy-budget bundle                                       */
/* ------------------------------------------------------------------------- */

template AccountBudgetBinding() {
    signal input sender_balance;
    signal input receiver_balance;
    signal input spent_window;
    signal input spent_private;
    signal input amount;
    signal input sender_new;
    signal input receiver_new;
    signal input window_limit;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component h = Poseidon(11);
    h.inputs[0] <== 1201;
    h.inputs[1] <== sender_balance;
    h.inputs[2] <== receiver_balance;
    h.inputs[3] <== spent_window;
    h.inputs[4] <== spent_private;
    h.inputs[5] <== amount;
    h.inputs[6] <== sender_new;
    h.inputs[7] <== receiver_new;
    h.inputs[8] <== window_limit;
    h.inputs[9] <== anonymity_budget;
    h.inputs[10] <== binding_randomness;
    h.out === tx_tag;
}

template LinkedAccountBudgetMonolithic(nBits) {
    signal input sender_balance;
    signal input receiver_balance;
    signal input spent_window;
    signal input spent_private;
    signal input amount;
    signal input sender_new;
    signal input receiver_new;
    signal input window_limit;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = AccountBudgetBinding();
    binding.sender_balance <== sender_balance;
    binding.receiver_balance <== receiver_balance;
    binding.spent_window <== spent_window;
    binding.spent_private <== spent_private;
    binding.amount <== amount;
    binding.sender_new <== sender_new;
    binding.receiver_new <== receiver_new;
    binding.window_limit <== window_limit;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = AccountPolicyWithPrivacyBudget(nBits);
    policy.sender_balance <== sender_balance;
    policy.receiver_balance <== receiver_balance;
    policy.spent_window <== spent_window;
    policy.spent_private <== spent_private;
    policy.amount <== amount;
    policy.sender_new <== sender_new;
    policy.receiver_new <== receiver_new;
    policy.window_limit <== window_limit;
    policy.anonymity_budget <== anonymity_budget;
}

template LinkedAccountBudgetValidity(nBits) {
    signal input sender_balance;
    signal input receiver_balance;
    signal input spent_window;
    signal input spent_private;
    signal input amount;
    signal input sender_new;
    signal input receiver_new;
    signal input window_limit;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = AccountBudgetBinding();
    binding.sender_balance <== sender_balance;
    binding.receiver_balance <== receiver_balance;
    binding.spent_window <== spent_window;
    binding.spent_private <== spent_private;
    binding.amount <== amount;
    binding.sender_new <== sender_new;
    binding.receiver_new <== receiver_new;
    binding.window_limit <== window_limit;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = LocalFinancialValidity(nBits);
    policy.balance <== sender_balance;
    policy.amount <== amount;
}

template LinkedAccountBudgetTransition(nBits) {
    signal input sender_balance;
    signal input receiver_balance;
    signal input spent_window;
    signal input spent_private;
    signal input amount;
    signal input sender_new;
    signal input receiver_new;
    signal input window_limit;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = AccountBudgetBinding();
    binding.sender_balance <== sender_balance;
    binding.receiver_balance <== receiver_balance;
    binding.spent_window <== spent_window;
    binding.spent_private <== spent_private;
    binding.amount <== amount;
    binding.sender_new <== sender_new;
    binding.receiver_new <== receiver_new;
    binding.window_limit <== window_limit;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = StateTransitionAndConservation(nBits);
    policy.sender_balance <== sender_balance;
    policy.receiver_balance <== receiver_balance;
    policy.amount <== amount;
    policy.sender_new <== sender_new;
    policy.receiver_new <== receiver_new;
}

template LinkedAccountBudgetLimit(nBits) {
    signal input sender_balance;
    signal input receiver_balance;
    signal input spent_window;
    signal input spent_private;
    signal input amount;
    signal input sender_new;
    signal input receiver_new;
    signal input window_limit;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = AccountBudgetBinding();
    binding.sender_balance <== sender_balance;
    binding.receiver_balance <== receiver_balance;
    binding.spent_window <== spent_window;
    binding.spent_private <== spent_private;
    binding.amount <== amount;
    binding.sender_new <== sender_new;
    binding.receiver_new <== receiver_new;
    binding.window_limit <== window_limit;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = OperatingLimit(nBits);
    policy.spent_window <== spent_window;
    policy.amount <== amount;
    policy.window_limit <== window_limit;
}

template LinkedAccountBudgetBudget(nBits) {
    signal input sender_balance;
    signal input receiver_balance;
    signal input spent_window;
    signal input spent_private;
    signal input amount;
    signal input sender_new;
    signal input receiver_new;
    signal input window_limit;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = AccountBudgetBinding();
    binding.sender_balance <== sender_balance;
    binding.receiver_balance <== receiver_balance;
    binding.spent_window <== spent_window;
    binding.spent_private <== spent_private;
    binding.amount <== amount;
    binding.sender_new <== sender_new;
    binding.receiver_new <== receiver_new;
    binding.window_limit <== window_limit;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = PrivacyBudget(nBits);
    policy.spent_private <== spent_private;
    policy.amount <== amount;
    policy.anonymity_budget <== anonymity_budget;
}

/* ------------------------------------------------------------------------- */
/* Token bundle                                                               */
/* ------------------------------------------------------------------------- */

template TokenBundleBinding() {
    signal input token_secret;
    signal input token_value;
    signal input token_randomness;
    signal input amount;
    signal input spent_private;
    signal input root;
    signal input nullifier;
    signal input nullifier_domain;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component h = Poseidon(11);
    h.inputs[0] <== 1301;
    h.inputs[1] <== token_secret;
    h.inputs[2] <== token_value;
    h.inputs[3] <== token_randomness;
    h.inputs[4] <== amount;
    h.inputs[5] <== spent_private;
    h.inputs[6] <== root;
    h.inputs[7] <== nullifier;
    h.inputs[8] <== nullifier_domain;
    h.inputs[9] <== anonymity_budget;
    h.inputs[10] <== binding_randomness;
    h.out === tx_tag;
}

template LinkedTokenBundleMonolithic(nBits, depth) {
    signal input token_secret;
    signal input token_value;
    signal input token_randomness;
    signal input amount;
    signal input spent_private;
    signal input root;
    signal input nullifier;
    signal input nullifier_domain;
    signal input anonymity_budget;
    signal input path_elements[depth];
    signal input path_indices[depth];
    signal input binding_randomness;
    signal input tx_tag;

    component binding = TokenBundleBinding();
    binding.token_secret <== token_secret;
    binding.token_value <== token_value;
    binding.token_randomness <== token_randomness;
    binding.amount <== amount;
    binding.spent_private <== spent_private;
    binding.root <== root;
    binding.nullifier <== nullifier;
    binding.nullifier_domain <== nullifier_domain;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = TokenPolicyBundle(nBits, depth);
    policy.token_secret <== token_secret;
    policy.token_value <== token_value;
    policy.token_randomness <== token_randomness;
    policy.amount <== amount;
    policy.spent_private <== spent_private;
    policy.root <== root;
    policy.nullifier <== nullifier;
    policy.nullifier_domain <== nullifier_domain;
    policy.anonymity_budget <== anonymity_budget;
    for (var i = 0; i < depth; i++) {
        policy.path_elements[i] <== path_elements[i];
        policy.path_indices[i] <== path_indices[i];
    }
}

template LinkedTokenBundleMembership(depth) {
    signal input token_secret;
    signal input token_value;
    signal input token_randomness;
    signal input amount;
    signal input spent_private;
    signal input root;
    signal input nullifier;
    signal input nullifier_domain;
    signal input anonymity_budget;
    signal input path_elements[depth];
    signal input path_indices[depth];
    signal input binding_randomness;
    signal input tx_tag;

    component binding = TokenBundleBinding();
    binding.token_secret <== token_secret;
    binding.token_value <== token_value;
    binding.token_randomness <== token_randomness;
    binding.amount <== amount;
    binding.spent_private <== spent_private;
    binding.root <== root;
    binding.nullifier <== nullifier;
    binding.nullifier_domain <== nullifier_domain;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component leafHash = Poseidon(3);
    leafHash.inputs[0] <== token_secret;
    leafHash.inputs[1] <== token_value;
    leafHash.inputs[2] <== token_randomness;

    component policy = MerkleMembership(depth);
    policy.leaf <== leafHash.out;
    policy.root <== root;
    for (var i = 0; i < depth; i++) {
        policy.path_elements[i] <== path_elements[i];
        policy.path_indices[i] <== path_indices[i];
    }
}

template LinkedTokenBundleNullifier() {
    signal input token_secret;
    signal input token_value;
    signal input token_randomness;
    signal input amount;
    signal input spent_private;
    signal input root;
    signal input nullifier;
    signal input nullifier_domain;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = TokenBundleBinding();
    binding.token_secret <== token_secret;
    binding.token_value <== token_value;
    binding.token_randomness <== token_randomness;
    binding.amount <== amount;
    binding.spent_private <== spent_private;
    binding.root <== root;
    binding.nullifier <== nullifier;
    binding.nullifier_domain <== nullifier_domain;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = NullifierCorrectness();
    policy.asset_secret <== token_secret;
    policy.nullifier_domain <== nullifier_domain;
    policy.nullifier <== nullifier;
}

template LinkedTokenBundleValidity(nBits) {
    signal input token_secret;
    signal input token_value;
    signal input token_randomness;
    signal input amount;
    signal input spent_private;
    signal input root;
    signal input nullifier;
    signal input nullifier_domain;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = TokenBundleBinding();
    binding.token_secret <== token_secret;
    binding.token_value <== token_value;
    binding.token_randomness <== token_randomness;
    binding.amount <== amount;
    binding.spent_private <== spent_private;
    binding.root <== root;
    binding.nullifier <== nullifier;
    binding.nullifier_domain <== nullifier_domain;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = LocalFinancialValidity(nBits);
    policy.balance <== token_value;
    policy.amount <== amount;
}

template LinkedTokenBundleBudget(nBits) {
    signal input token_secret;
    signal input token_value;
    signal input token_randomness;
    signal input amount;
    signal input spent_private;
    signal input root;
    signal input nullifier;
    signal input nullifier_domain;
    signal input anonymity_budget;
    signal input binding_randomness;
    signal input tx_tag;

    component binding = TokenBundleBinding();
    binding.token_secret <== token_secret;
    binding.token_value <== token_value;
    binding.token_randomness <== token_randomness;
    binding.amount <== amount;
    binding.spent_private <== spent_private;
    binding.root <== root;
    binding.nullifier <== nullifier;
    binding.nullifier_domain <== nullifier_domain;
    binding.anonymity_budget <== anonymity_budget;
    binding.binding_randomness <== binding_randomness;
    binding.tx_tag <== tx_tag;

    component policy = PrivacyBudget(nBits);
    policy.spent_private <== spent_private;
    policy.amount <== amount;
    policy.anonymity_budget <== anonymity_budget;
}
