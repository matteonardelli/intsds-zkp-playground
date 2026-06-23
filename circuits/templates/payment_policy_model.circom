pragma circom 2.1.6;

include "circomlib/circuits/bitify.circom";
include "circomlib/circuits/comparators.circom";
include "circomlib/circuits/poseidon.circom";

/*
 * Policy kernels for the policy model described in sec_policymodel.tex.
 *
 * Scope represented by this file:
 *   - pi_valid:  local financial validity
 *   - pi_limit:  operating/regulatory limits
 *   - pi_budget: privacy/anonymity budgets
 *   - pi_trans:  state transition and value conservation
 *   - pi_mem:    membership and nullifier correctness
 *
 * Authorization, audit/disclosure/tracing, and privacy-structure policies
 * are deliberately not reduced to generic Circom circuits here: the paper
 * treats them as protocol-specific and outside the initial experimental scope.
 *
 * IMPORTANT: these are policy kernels, not complete payment protocols. In a
 * complete system, private values such as `amount` and balances must be bound
 * to transaction commitments, ciphertexts, authenticated state, or other
 * protocol objects. The benchmark circuits isolate the enforcement cost of
 * the policy predicates themselves.
 */

/* Enforce that x is an unsigned n-bit integer. */
template Unsigned(nBits) {
    assert(nBits > 0);
    assert(nBits <= 252);

    signal input x;

    component bits = Num2Bits(nBits);
    bits.in <== x;
}

/* Enforce that x is a strictly positive unsigned n-bit integer. */
template PositiveUnsigned(nBits) {
    signal input x;

    component range = Unsigned(nBits);
    range.x <== x;

    component isZero = IsZero();
    isZero.in <== x;
    isZero.out === 0;
}

/*
 * pi_valid -- Local financial validity.
 *
 * Proves that the private transaction amount is positive and does not exceed
 * the private available balance:
 *
 *     0 < amount <= balance < 2^nBits.
 *
 * Both inputs are private in the canonical benchmark wrappers. A complete
 * payment system must bind them to the actual transaction state.
 */
template LocalFinancialValidity(nBits) {
    signal input balance;
    signal input amount;

    component balanceRange = Unsigned(nBits);
    balanceRange.x <== balance;

    component amountPositive = PositiveUnsigned(nBits);
    amountPositive.x <== amount;

    component enoughBalance = LessEqThan(nBits);
    enoughBalance.in[0] <== amount;
    enoughBalance.in[1] <== balance;
    enoughBalance.out === 1;
}

/*
 * pi_limit -- Operating/regulatory limit.
 *
 * Proves that a private cumulative counter remains below a public policy
 * threshold after the private transaction amount is added:
 *
 *     spent_window + amount <= window_limit.
 *
 * The (nBits+1)-bit intermediate prevents an n-bit overflow from silently
 * changing the intended unsigned-integer semantics.
 */
template OperatingLimit(nBits) {
    signal input spent_window;
    signal input amount;
    signal input window_limit;

    signal total_spent;

    component spentRange = Unsigned(nBits);
    component amountRange = Unsigned(nBits);
    component limitRange = Unsigned(nBits);

    spentRange.x <== spent_window;
    amountRange.x <== amount;
    limitRange.x <== window_limit;

    total_spent <== spent_window + amount;

    component totalRange = Unsigned(nBits + 1);
    totalRange.x <== total_spent;

    component withinLimit = LessEqThan(nBits + 1);
    withinLimit.in[0] <== total_spent;
    withinLimit.in[1] <== window_limit;
    withinLimit.out === 1;
}

/*
 * pi_budget -- Privacy/anonymity budget.
 *
 * Proves that private spending under the strong-privacy regime remains below
 * a public anonymity budget:
 *
 *     spent_private + amount <= anonymity_budget.
 *
 * This predicate is arithmetically isomorphic to OperatingLimit, but it is kept
 * as a distinct policy class because its system semantics are different: when
 * the budget is exhausted, the payment may still be allowed under a less
 * private or auditable mode.
 */
template PrivacyBudget(nBits) {
    signal input spent_private;
    signal input amount;
    signal input anonymity_budget;

    signal total_private_spent;

    component spentRange = Unsigned(nBits);
    component amountRange = Unsigned(nBits);
    component budgetRange = Unsigned(nBits);

    spentRange.x <== spent_private;
    amountRange.x <== amount;
    budgetRange.x <== anonymity_budget;

    total_private_spent <== spent_private + amount;

    component totalRange = Unsigned(nBits + 1);
    totalRange.x <== total_private_spent;

    component withinBudget = LessEqThan(nBits + 1);
    withinBudget.in[0] <== total_private_spent;
    withinBudget.in[1] <== anonymity_budget;
    withinBudget.out === 1;
}

/*
 * pi_trans -- State transition and value conservation.
 *
 * Proves the account-style transition:
 *
 *     sender_balance   = sender_new + amount
 *     receiver_new     = receiver_balance + amount
 *     sender_balance + receiver_balance
 *                       = sender_new + receiver_new.
 *
 * Explicit n-bit range constraints preserve unsigned semantics and prevent a
 * field-arithmetic underflow from being interpreted as a valid balance.
 * The conservation equation is stated explicitly for traceability to the
 * policy model, although it is logically implied by the two update equations
 * and may be optimized by the compiler.
 */
template StateTransitionAndConservation(nBits) {
    signal input sender_balance;
    signal input receiver_balance;
    signal input amount;
    signal input sender_new;
    signal input receiver_new;

    signal total_before;
    signal total_after;

    component senderRange = Unsigned(nBits);
    component receiverRange = Unsigned(nBits);
    component amountRange = Unsigned(nBits);
    component senderNewRange = Unsigned(nBits);
    component receiverNewRange = Unsigned(nBits);

    senderRange.x <== sender_balance;
    receiverRange.x <== receiver_balance;
    amountRange.x <== amount;
    senderNewRange.x <== sender_new;
    receiverNewRange.x <== receiver_new;

    sender_balance === sender_new + amount;
    receiver_new === receiver_balance + amount;

    total_before <== sender_balance + receiver_balance;
    total_after <== sender_new + receiver_new;
    total_before === total_after;
}

/*
 * pi_mem -- Merkle membership.
 *
 * Proves that a private leaf and private authentication path lead to the
 * public Merkle root. Poseidon is used as a ZK-friendly two-to-one hash.
 *
 * path_indices[i] = 0: the current node is the left child.
 * path_indices[i] = 1: the current node is the right child.
 */
template MerkleMembership(depth) {
    assert(depth > 0);

    signal input leaf;
    signal input root;
    signal input path_elements[depth];
    signal input path_indices[depth];

    signal current[depth + 1];
    signal left[depth];
    signal right[depth];

    component hashes[depth];

    current[0] <== leaf;

    for (var i = 0; i < depth; i++) {
        path_indices[i] * (path_indices[i] - 1) === 0;

        // One multiplication per selector constraint (R1CS-compatible mux).
        left[i] <== current[i]
                 + path_indices[i] * (path_elements[i] - current[i]);
        right[i] <== path_elements[i]
                  + path_indices[i] * (current[i] - path_elements[i]);

        hashes[i] = Poseidon(2);
        hashes[i].inputs[0] <== left[i];
        hashes[i].inputs[1] <== right[i];
        current[i + 1] <== hashes[i].out;
    }

    current[depth] === root;
}

/*
 * pi_mem -- Nullifier correctness component.
 *
 * Proves that the public nullifier is correctly derived from a private asset
 * secret and a public domain/context value:
 *
 *     nullifier = Poseidon(asset_secret, nullifier_domain).
 *
 * This circuit does NOT prove non-spentness by itself. Non-spentness requires
 * an external ledger/state check that the public nullifier has not appeared
 * before. The circuit only proves correct linkage to the hidden asset secret.
 */
template NullifierCorrectness() {
    signal input asset_secret;
    signal input nullifier_domain;
    signal input nullifier;

    component h = Poseidon(2);
    h.inputs[0] <== asset_secret;
    h.inputs[1] <== nullifier_domain;
    h.out === nullifier;
}

/*
 * pi_valid AND pi_limit.
 *
 * A compact two-policy composition used to study the cost of enforcing local
 * validity and a cumulative regulatory limit in one proof. Range constraints
 * are shared across policy predicates where possible.
 */
template LocalValidityAndOperatingLimit(nBits) {
    signal input balance;
    signal input spent_window;
    signal input amount;
    signal input window_limit;

    signal total_spent;

    component balanceRange = Unsigned(nBits);
    component spentRange = Unsigned(nBits);
    component amountPositive = PositiveUnsigned(nBits);
    component limitRange = Unsigned(nBits);

    balanceRange.x <== balance;
    spentRange.x <== spent_window;
    amountPositive.x <== amount;
    limitRange.x <== window_limit;

    component enoughBalance = LessEqThan(nBits);
    enoughBalance.in[0] <== amount;
    enoughBalance.in[1] <== balance;
    enoughBalance.out === 1;

    total_spent <== spent_window + amount;

    component totalRange = Unsigned(nBits + 1);
    totalRange.x <== total_spent;

    component withinLimit = LessEqThan(nBits + 1);
    withinLimit.in[0] <== total_spent;
    withinLimit.in[1] <== window_limit;
    withinLimit.out === 1;
}

/*
 * pi_valid AND pi_trans AND pi_limit.
 *
 * Representative account-based policy core. This corresponds to the former
 * `balance_limit_and_conservation` benchmark but uses explicit unsigned range
 * constraints and private transaction values.
 */
template AccountPolicyCore(nBits) {
    signal input sender_balance;
    signal input receiver_balance;
    signal input spent_window;
    signal input amount;
    signal input sender_new;
    signal input receiver_new;
    signal input window_limit;

    signal total_spent;
    signal total_before;
    signal total_after;

    component senderRange = Unsigned(nBits);
    component receiverRange = Unsigned(nBits);
    component spentRange = Unsigned(nBits);
    component amountPositive = PositiveUnsigned(nBits);
    component senderNewRange = Unsigned(nBits);
    component receiverNewRange = Unsigned(nBits);
    component limitRange = Unsigned(nBits);

    senderRange.x <== sender_balance;
    receiverRange.x <== receiver_balance;
    spentRange.x <== spent_window;
    amountPositive.x <== amount;
    senderNewRange.x <== sender_new;
    receiverNewRange.x <== receiver_new;
    limitRange.x <== window_limit;

    component enoughBalance = LessEqThan(nBits);
    enoughBalance.in[0] <== amount;
    enoughBalance.in[1] <== sender_balance;
    enoughBalance.out === 1;

    sender_balance === sender_new + amount;
    receiver_new === receiver_balance + amount;

    total_before <== sender_balance + receiver_balance;
    total_after <== sender_new + receiver_new;
    total_before === total_after;

    total_spent <== spent_window + amount;

    component totalSpentRange = Unsigned(nBits + 1);
    totalSpentRange.x <== total_spent;

    component withinLimit = LessEqThan(nBits + 1);
    withinLimit.in[0] <== total_spent;
    withinLimit.in[1] <== window_limit;
    withinLimit.out === 1;
}

/*
 * pi_valid AND pi_trans AND pi_limit AND pi_budget.
 *
 * Representative account-based private-payment bundle. It extends
 * AccountPolicyCore with a distinct anonymity-budget predicate. Even though
 * the two cumulative inequalities have the same arithmetic shape, they model
 * different system semantics and therefore remain separate policy checks.
 */
template AccountPolicyWithPrivacyBudget(nBits) {
    signal input sender_balance;
    signal input receiver_balance;
    signal input spent_window;
    signal input spent_private;
    signal input amount;
    signal input sender_new;
    signal input receiver_new;
    signal input window_limit;
    signal input anonymity_budget;

    signal total_spent;
    signal total_private_spent;
    signal total_before;
    signal total_after;

    component senderRange = Unsigned(nBits);
    component receiverRange = Unsigned(nBits);
    component spentRange = Unsigned(nBits);
    component privateSpentRange = Unsigned(nBits);
    component amountPositive = PositiveUnsigned(nBits);
    component senderNewRange = Unsigned(nBits);
    component receiverNewRange = Unsigned(nBits);
    component limitRange = Unsigned(nBits);
    component budgetRange = Unsigned(nBits);

    senderRange.x <== sender_balance;
    receiverRange.x <== receiver_balance;
    spentRange.x <== spent_window;
    privateSpentRange.x <== spent_private;
    amountPositive.x <== amount;
    senderNewRange.x <== sender_new;
    receiverNewRange.x <== receiver_new;
    limitRange.x <== window_limit;
    budgetRange.x <== anonymity_budget;

    component enoughBalance = LessEqThan(nBits);
    enoughBalance.in[0] <== amount;
    enoughBalance.in[1] <== sender_balance;
    enoughBalance.out === 1;

    sender_balance === sender_new + amount;
    receiver_new === receiver_balance + amount;

    total_before <== sender_balance + receiver_balance;
    total_after <== sender_new + receiver_new;
    total_before === total_after;

    total_spent <== spent_window + amount;
    total_private_spent <== spent_private + amount;

    component totalSpentRange = Unsigned(nBits + 1);
    component totalPrivateRange = Unsigned(nBits + 1);
    totalSpentRange.x <== total_spent;
    totalPrivateRange.x <== total_private_spent;

    component withinLimit = LessEqThan(nBits + 1);
    withinLimit.in[0] <== total_spent;
    withinLimit.in[1] <== window_limit;
    withinLimit.out === 1;

    component withinBudget = LessEqThan(nBits + 1);
    withinBudget.in[0] <== total_private_spent;
    withinBudget.in[1] <== anonymity_budget;
    withinBudget.out === 1;
}

/*
 * pi_mem AND pi_valid AND pi_budget, plus nullifier correctness.
 *
 * Representative token-style policy bundle:
 *   1. derive a private token leaf from secret/value/randomness;
 *   2. prove that the leaf belongs to the public Merkle root;
 *   3. derive the public nullifier from the same private secret;
 *   4. prove that the hidden token value covers the hidden amount;
 *   5. prove that the hidden amount remains within the anonymity budget.
 *
 * As above, ledger-level non-reuse of the nullifier is checked outside the
 * circuit. The amount remains private and is shared across the predicates in
 * this single proof.
 */
template TokenPolicyBundle(nBits, depth) {
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

    signal leaf;
    signal total_private_spent;

    component valueRange = Unsigned(nBits);
    component amountPositive = PositiveUnsigned(nBits);
    component spentRange = Unsigned(nBits);
    component budgetRange = Unsigned(nBits);

    valueRange.x <== token_value;
    amountPositive.x <== amount;
    spentRange.x <== spent_private;
    budgetRange.x <== anonymity_budget;

    component leafHash = Poseidon(3);
    leafHash.inputs[0] <== token_secret;
    leafHash.inputs[1] <== token_value;
    leafHash.inputs[2] <== token_randomness;
    leaf <== leafHash.out;

    component membership = MerkleMembership(depth);
    membership.leaf <== leaf;
    membership.root <== root;
    for (var i = 0; i < depth; i++) {
        membership.path_elements[i] <== path_elements[i];
        membership.path_indices[i] <== path_indices[i];
    }

    component nullifierCheck = NullifierCorrectness();
    nullifierCheck.asset_secret <== token_secret;
    nullifierCheck.nullifier_domain <== nullifier_domain;
    nullifierCheck.nullifier <== nullifier;

    component enoughValue = LessEqThan(nBits);
    enoughValue.in[0] <== amount;
    enoughValue.in[1] <== token_value;
    enoughValue.out === 1;

    total_private_spent <== spent_private + amount;

    component totalPrivateRange = Unsigned(nBits + 1);
    totalPrivateRange.x <== total_private_spent;

    component withinBudget = LessEqThan(nBits + 1);
    withinBudget.in[0] <== total_private_spent;
    withinBudget.in[1] <== anonymity_budget;
    withinBudget.out === 1;
}
