# ZKP-based Policy Enforcement in Payment Systems

This repository contains circuits and experimental scripts to evaluate the cost of enforcing payment policies using Zero-Knowledge Proofs (ZKPs).

## Overview

Modern privacy-preserving payment systems (e.g., Platypus, PEREDI, UTT) rely on ZKPs to enforce constraints such as:

- sufficient balance
- transaction limits
- cumulative spending limits

Instead of implementing full systems, this project isolates representative policy constraints and evaluates their cost when encoded as ZKP circuits.

### Circuits

The repository includes the following circuits:

#### 1. Sufficient Balance

```
balance >= amount
```
- Represents local correctness
- Inspired by account-based systems (e.g., Platypus)

#### 2. Cumulative Limit

```
spent_window + amount <= limit
```

- Represents regulatory constraints
- Inspired by PEREDI / UTT


#### 3. Balance + Limit (composed)

```
balance >= amount
AND
spent_window + amount <= limit
```

- Minimal realistic combination of correctness + compliance


#### 4. Balance + Limit + Conservation

- Adds state update consistency
- Closer to full transaction logic


## Requirements

- Python 3.9+
- Node.js
- circom
- snarkjs

## Setup

### circomlib
After cloning the repository, in the root folder, run: 

```bash
npm install 
```

### Powers of Tau
The `.ptau` file is already in the root folder of the project. If needed, you can download it from `https://hermez.s3-eu-west-1.amazonaws.com/powersOfTau28_hez_final_12.ptau` and place it in the project root.



## Usage and Experiment Running

### 1. Run benchmarks

```bash
python scripts/run_bench.sh
``` 

For each circuit, this measures:

* number of constraints
* witness generation time
* proving time
* verification time
* proof size

This generates:

* results/bench_results.csv which summarizes the experiments

### 2. Generate tables

```bash
python scripts/build_table.py
```

This generates: 
* table in textual format (`.txt`)
* table in LaTeX format (`.tex`)

### 3. Generate plots

```bash
python scripts/plot_results.py
```

This produces:

* constraints vs bit-width
* proving time vs bit-width
* verification time vs bit-width
