# Validation

The aligned source tree was checked with:

- Circom compiler 2.2.2 (all files declare `pragma circom 2.1.6`);
- circomlib 2.0.5.

## Compilation checks

All canonical wrappers and all legacy compatibility wrappers were compiled to
R1CS successfully.

## Witness checks

Valid witnesses were generated successfully for representative 32-bit or
depth-8 instances of:

- local financial validity;
- operating limit;
- privacy budget;
- state transition and value conservation;
- local-validity + operating-limit composition;
- account policy core;
- account policy with privacy budget;
- Poseidon Merkle membership;
- Poseidon nullifier correctness;
- token policy bundle.

Poseidon roots and nullifiers used in the membership checks were computed with
circomlibjs only for validation. Input-generation scripts are intentionally
left for the forthcoming evaluation-harness revision.
