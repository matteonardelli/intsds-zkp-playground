#!/usr/bin/env node
"use strict";

/**
 * Generate deterministic valid inputs for the first policy-model campaign.
 *
 * Requirements:
 *   npm install
 *
 * The repository package.json must include circomlibjs. All integer values are
 * serialized as decimal strings to avoid JavaScript number truncation.
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
  const outputPath = path.join(outDir, `${name}.json`);
  fs.writeFileSync(
    outputPath,
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
  const windowLimit = amount * 5n;
  const anonymityBudget = amount * 4n;
  const senderNew = senderBalance - amount;
  const receiverNew = receiverBalance + amount;

  return {
    amount,
    balance: senderBalance,
    sender_balance: senderBalance,
    receiver_balance: receiverBalance,
    sender_new: senderNew,
    receiver_new: receiverNew,
    spent_window: spentWindow,
    spent_private: spentPrivate,
    window_limit: windowLimit,
    anonymity_budget: anonymityBudget,
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

  return {
    root: current,
    path_elements: pathElements,
    path_indices: pathIndices,
  };
}

async function main() {
  const { outDir, seed } = parseArgs();
  fs.mkdirSync(outDir, { recursive: true });

  const poseidon = await buildPoseidon();

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

  const metadata = {
    seed,
    generated_at_utc: new Date().toISOString(),
    field_prime: FIELD_PRIME.toString(10),
    bits: BITS,
    merkle_depths: DEPTHS,
    note:
      "Deterministic valid inputs for performance experiments; all large integers are decimal strings.",
  };
  fs.writeFileSync(
    path.join(outDir, "_metadata.json"),
    `${JSON.stringify(metadata, null, 2)}\n`,
    "utf8"
  );

  console.log(`Generated valid inputs in ${outDir}`);
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
