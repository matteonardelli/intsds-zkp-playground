#!/usr/bin/env node
"use strict";

/**
 * Generate deterministic valid inputs for the complete policy-kernel campaign.
 *
 * One generator serves the core, linked, and paper campaign profiles. All
 * values are serialized as decimal strings to avoid JavaScript truncation.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { buildPoseidon } = require("circomlibjs");

const FIELD_PRIME = BigInt(
  "21888242871839275222246405745257275088548364400416034343698204186575808495617"
);
const BITS = [16, 32, 64];
const DEPTHS = [8, 16, 32];
const DOMAIN_VALID_LIMIT = 1101n;
const DOMAIN_ACCOUNT_BUDGET = 1201n;
const DOMAIN_TOKEN_BUNDLE = 1301n;

function parseArgs() {
  const args = process.argv.slice(2);
  const result = {
    outDir: path.resolve(process.cwd(), "inputs", "valid"),
    seed: "20260623",
  };
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--out-dir") {
      result.outDir = path.resolve(args[++i]);
    } else if (args[i] === "--seed") {
      result.seed = String(args[++i]);
    } else if (args[i] === "--help" || args[i] === "-h") {
      console.log(
        "Usage: node scripts/generate_inputs.js [--out-dir PATH] [--seed VALUE]"
      );
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${args[i]}`);
    }
  }
  return result;
}

function deterministicField(seed, label) {
  const digest = crypto
    .createHash("sha256")
    .update(`${seed}:${label}`, "utf8")
    .digest("hex");
  return BigInt(`0x${digest}`) % FIELD_PRIME;
}

function stringifyBigInts(value) {
  if (typeof value === "bigint") return value.toString(10);
  if (Array.isArray(value)) return value.map(stringifyBigInts);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, val]) => [key, stringifyBigInts(val)])
    );
  }
  return value;
}

function writeJson(outDir, name, payload) {
  fs.writeFileSync(
    path.join(outDir, `${name}.json`),
    `${JSON.stringify(stringifyBigInts(payload), null, 2)}\n`,
    "utf8"
  );
}

function arithmeticValues(bits) {
  const max = (1n << BigInt(bits)) - 1n;
  const amount = max / 32n;
  const senderBalance = amount * 8n;
  const receiverBalance = amount * 3n;
  const spentWindow = amount * 2n;
  const spentPrivate = amount;
  return {
    amount,
    balance: senderBalance,
    sender_balance: senderBalance,
    receiver_balance: receiverBalance,
    sender_new: senderBalance - amount,
    receiver_new: receiverBalance + amount,
    spent_window: spentWindow,
    spent_private: spentPrivate,
    window_limit: amount * 5n,
    anonymity_budget: amount * 4n,
  };
}

function poseidonValue(poseidon, values) {
  return BigInt(poseidon.F.toObject(poseidon(values)));
}

function buildMerklePath(poseidon, leaf, depth, seed, namespace) {
  const pathElements = [];
  const pathIndices = [];
  let current = leaf;
  for (let level = 0; level < depth; level += 1) {
    const sibling = deterministicField(seed, `${namespace}:sibling:${level}`);
    const index = level % 2;
    pathElements.push(sibling);
    pathIndices.push(index);
    current =
      index === 0
        ? poseidonValue(poseidon, [current, sibling])
        : poseidonValue(poseidon, [sibling, current]);
  }
  return { root: current, path_elements: pathElements, path_indices: pathIndices };
}

function generateCoreInputs(outDir, seed, poseidon) {
  for (const bits of BITS) {
    const v = arithmeticValues(bits);

    writeJson(outDir, `local_financial_validity_${bits}`, {
      balance: v.balance,
      amount: v.amount,
    });
    writeJson(outDir, `operating_limit_${bits}`, {
      spent_window: v.spent_window,
      amount: v.amount,
      window_limit: v.window_limit,
    });
    writeJson(outDir, `privacy_budget_${bits}`, {
      spent_private: v.spent_private,
      amount: v.amount,
      anonymity_budget: v.anonymity_budget,
    });
    writeJson(outDir, `state_transition_and_conservation_${bits}`, {
      sender_balance: v.sender_balance,
      receiver_balance: v.receiver_balance,
      amount: v.amount,
      sender_new: v.sender_new,
      receiver_new: v.receiver_new,
    });
    writeJson(outDir, `local_validity_and_operating_limit_${bits}`, {
      balance: v.balance,
      spent_window: v.spent_window,
      amount: v.amount,
      window_limit: v.window_limit,
    });
    writeJson(outDir, `account_policy_core_${bits}`, {
      sender_balance: v.sender_balance,
      receiver_balance: v.receiver_balance,
      spent_window: v.spent_window,
      amount: v.amount,
      sender_new: v.sender_new,
      receiver_new: v.receiver_new,
      window_limit: v.window_limit,
    });
    writeJson(outDir, `account_policy_with_privacy_budget_${bits}`, {
      sender_balance: v.sender_balance,
      receiver_balance: v.receiver_balance,
      spent_window: v.spent_window,
      spent_private: v.spent_private,
      amount: v.amount,
      sender_new: v.sender_new,
      receiver_new: v.receiver_new,
      window_limit: v.window_limit,
      anonymity_budget: v.anonymity_budget,
    });
  }

  for (const depth of DEPTHS) {
    const leaf = deterministicField(seed, `standalone-merkle:${depth}:leaf`);
    const merkle = buildMerklePath(
      poseidon,
      leaf,
      depth,
      seed,
      `standalone-merkle:${depth}`
    );
    writeJson(outDir, `merkle_membership_depth_${depth}`, {
      leaf,
      root: merkle.root,
      path_elements: merkle.path_elements,
      path_indices: merkle.path_indices,
    });
  }

  const nullifierSecret = deterministicField(seed, "nullifier:secret");
  const nullifierDomain = deterministicField(seed, "nullifier:domain");
  const nullifier = poseidonValue(poseidon, [nullifierSecret, nullifierDomain]);
  writeJson(outDir, "nullifier_correctness_poseidon", {
    asset_secret: nullifierSecret,
    nullifier_domain: nullifierDomain,
    nullifier,
  });

  const tokenValues = arithmeticValues(32);
  for (const depth of DEPTHS) {
    const tokenSecret = deterministicField(seed, `token:${depth}:secret`);
    const tokenRandomness = deterministicField(seed, `token:${depth}:randomness`);
    const tokenLeaf = poseidonValue(poseidon, [
      tokenSecret,
      tokenValues.balance,
      tokenRandomness,
    ]);
    const tokenMerkle = buildMerklePath(
      poseidon,
      tokenLeaf,
      depth,
      seed,
      `token:${depth}`
    );
    const domain = deterministicField(seed, `token:${depth}:nullifier-domain`);
    const tokenNullifier = poseidonValue(poseidon, [tokenSecret, domain]);

    writeJson(outDir, `token_policy_bundle_32_depth_${depth}`, {
      token_secret: tokenSecret,
      token_value: tokenValues.balance,
      token_randomness: tokenRandomness,
      amount: tokenValues.amount,
      spent_private: tokenValues.spent_private,
      root: tokenMerkle.root,
      nullifier: tokenNullifier,
      nullifier_domain: domain,
      anonymity_budget: tokenValues.anonymity_budget,
      path_elements: tokenMerkle.path_elements,
      path_indices: tokenMerkle.path_indices,
    });
  }
}

function generateLinkedInputs(outDir, seed, poseidon) {
  const v = arithmeticValues(32);

  const validLimitRandomness = deterministicField(seed, "linked:valid-limit:blinding");
  const validLimitTag = poseidonValue(poseidon, [
    DOMAIN_VALID_LIMIT,
    v.balance,
    v.spent_window,
    v.amount,
    v.window_limit,
    validLimitRandomness,
  ]);
  const validLimitPayload = {
    balance: v.balance,
    spent_window: v.spent_window,
    amount: v.amount,
    window_limit: v.window_limit,
    binding_randomness: validLimitRandomness,
    tx_tag: validLimitTag,
  };
  for (const name of [
    "linked_valid_limit_monolithic_32",
    "linked_valid_limit_validity_32",
    "linked_valid_limit_limit_32",
  ]) {
    writeJson(outDir, name, validLimitPayload);
  }

  const accountRandomness = deterministicField(seed, "linked:account-budget:blinding");
  const accountTag = poseidonValue(poseidon, [
    DOMAIN_ACCOUNT_BUDGET,
    v.sender_balance,
    v.receiver_balance,
    v.spent_window,
    v.spent_private,
    v.amount,
    v.sender_new,
    v.receiver_new,
    v.window_limit,
    v.anonymity_budget,
    accountRandomness,
  ]);
  const accountPayload = {
    sender_balance: v.sender_balance,
    receiver_balance: v.receiver_balance,
    spent_window: v.spent_window,
    spent_private: v.spent_private,
    amount: v.amount,
    sender_new: v.sender_new,
    receiver_new: v.receiver_new,
    window_limit: v.window_limit,
    anonymity_budget: v.anonymity_budget,
    binding_randomness: accountRandomness,
    tx_tag: accountTag,
  };
  for (const name of [
    "linked_account_budget_monolithic_32",
    "linked_account_budget_validity_32",
    "linked_account_budget_transition_32",
    "linked_account_budget_limit_32",
    "linked_account_budget_budget_32",
  ]) {
    writeJson(outDir, name, accountPayload);
  }

  const depth = 16;
  const tokenSecret = deterministicField(seed, "linked:token:secret");
  const tokenRandomness = deterministicField(seed, "linked:token:randomness");
  const nullifierDomain = deterministicField(seed, "linked:token:nullifier-domain");
  const tokenLeaf = poseidonValue(poseidon, [tokenSecret, v.balance, tokenRandomness]);
  const merkle = buildMerklePath(
    poseidon,
    tokenLeaf,
    depth,
    seed,
    "linked:token:depth16"
  );
  const nullifier = poseidonValue(poseidon, [tokenSecret, nullifierDomain]);
  const tokenBindingRandomness = deterministicField(seed, "linked:token:blinding");
  const tokenTag = poseidonValue(poseidon, [
    DOMAIN_TOKEN_BUNDLE,
    tokenSecret,
    v.balance,
    tokenRandomness,
    v.amount,
    v.spent_private,
    merkle.root,
    nullifier,
    nullifierDomain,
    v.anonymity_budget,
    tokenBindingRandomness,
  ]);
  const tokenCommon = {
    token_secret: tokenSecret,
    token_value: v.balance,
    token_randomness: tokenRandomness,
    amount: v.amount,
    spent_private: v.spent_private,
    root: merkle.root,
    nullifier,
    nullifier_domain: nullifierDomain,
    anonymity_budget: v.anonymity_budget,
    binding_randomness: tokenBindingRandomness,
    tx_tag: tokenTag,
  };
  const tokenWithPath = {
    ...tokenCommon,
    path_elements: merkle.path_elements,
    path_indices: merkle.path_indices,
  };
  writeJson(outDir, "linked_token_bundle_monolithic_32_depth_16", tokenWithPath);
  writeJson(outDir, "linked_token_bundle_membership_32_depth_16", tokenWithPath);
  for (const name of [
    "linked_token_bundle_nullifier_32_depth_16",
    "linked_token_bundle_validity_32_depth_16",
    "linked_token_bundle_budget_32_depth_16",
  ]) {
    writeJson(outDir, name, tokenCommon);
  }
}

async function main() {
  const { outDir, seed } = parseArgs();
  fs.mkdirSync(outDir, { recursive: true });
  const poseidon = await buildPoseidon();

  generateCoreInputs(outDir, seed, poseidon);
  generateLinkedInputs(outDir, seed, poseidon);

  const metadata = {
    seed,
    generated_at_utc: new Date().toISOString(),
    field_prime: FIELD_PRIME.toString(10),
    bits: BITS,
    merkle_depths: DEPTHS,
    linked_configurations: [
      "valid_limit_b32",
      "account_budget_b32",
      "token_bundle_b32_d16",
    ],
    binding_domains: {
      valid_limit: DOMAIN_VALID_LIMIT.toString(10),
      account_budget: DOMAIN_ACCOUNT_BUDGET.toString(10),
      token_bundle: DOMAIN_TOKEN_BUNDLE.toString(10),
    },
    note:
      "Deterministic valid inputs for the complete core+linked paper campaign.",
  };
  fs.writeFileSync(
    path.join(outDir, "_metadata.json"),
    `${JSON.stringify(metadata, null, 2)}\n`,
    "utf8"
  );
  console.log(`Generated complete campaign inputs in ${outDir}`);
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
