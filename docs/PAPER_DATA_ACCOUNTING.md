# Paper Data Accounting

This page fixes the counting convention for the final Qwen3-generated and Qwen3-verified release.

## Final Pipeline

- Generator: `Qwen3-30B-A3B-Instruct-2507`, text-only, greedy decoding.
- Programmatic stage: exact local replacement plus deterministic type, format, quotation, length, and overlap checks.
- Verifier: a separately loaded `Qwen3-30B-A3B-Instruct-2507`, text-only, greedy decoding.
- Retention: matching observed type, target error present, non-target content preserved, fluent, and quality score at least 3/5.

Only records produced by this final generator-verifier configuration and accepted by all validation gates are included.

## Exact Counts

| Quantity | Train | Validation | Total |
|---|---:|---:|---:|
| Source preference samples | 1,618 | 563 | 2,181 |
| Newly generated verified controlled negatives | 2,908 | 944 | 3,852 |
| Original rejected pairs | 1,618 | 563 | 2,181 |
| Canonical five-type preference pairs | 4,526 | 1,507 | 6,033 |
| Position-balanced pair rows | 9,052 | 3,014 | 12,066 |

The identity is:

```text
canonical five-type pairs
= original rejected pairs + verified controlled negatives

position-balanced rows
= 2 × canonical five-type pairs
```

## Generated Counts by Type

| Controlled error type | Train | Validation | Total |
|---|---:|---:|---:|
| Emotion Flip | 749 | 317 | 1,066 |
| Intensity Mismatch | 405 | 99 | 504 |
| Evidence Contradiction | 1,103 | 342 | 1,445 |
| Modality Omission | 651 | 186 | 837 |
| **All generated types** | **2,908** | **944** | **3,852** |

## Recommended Paper Wording

Use this sentence when describing newly constructed data:

> The final construction pipeline produced 3,852 Qwen3-verified controlled negatives, including 2,908 training and 944 validation instances across four error types.

Use this sentence when describing the complete preference data:

> After combining the controlled negatives with 2,181 original rejected pairs, the canonical five-type dataset contained 4,526 training and 1,507 validation preference pairs. Candidate-order balancing doubled these to 9,052 and 3,014 rows, respectively.

Do not describe 9,052 and 3,014 as newly generated negative descriptions; those values include original rejected pairs and positional duplication.
