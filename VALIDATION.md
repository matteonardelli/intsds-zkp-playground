# Validation

The circuits were developed for Circom 2.2.x with circomlib 2.0.5. Functional
validation covers valid, boundary, and invalid instances for:

- local financial validity;
- operating limits;
- privacy budgets;
- state transition and value conservation;
- Merkle membership;
- nullifier derivation;
- account- and token-oriented compositions;
- incorrect transaction commitments;
- mismatched commitments across otherwise valid component proofs.

Run the complete validation profile with:

```bash
python3 scripts/validate_circuits.py --scope all
```

Static manifest and post-processing checks are available through:

```bash
python3 -m unittest discover -s tests
```
