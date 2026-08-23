# EAPO-EmoPrefer

EAPO-EmoPrefer is the controlled error-augmented preference dataset introduced in **Error-Augmented Preference Optimization (EAPO)**. It extends human-annotated multimodal emotion preference pairs with fluent but intentionally unreliable descriptions covering four controlled error types.

The repository contains the released dataset, Qwen3-based construction and verification code, and the evaluation results reported in the paper. It does not include SFT/DPO training code, model weights, or source audio/video files.

## Dataset Composition

The following counts use the same convention as the paper.

| Dataset | Role | Preference pairs |
|---|---|---:|
| EmoPrefer-Data-V2 | Normal training | 1,618 |
| EAPO Error-Aug Train-Set | Error-augmented training | 4,526 |
| EmoPrefer-Data | Original validation | 563 |
| EAPO Error-Aug Val-Set | Controlled-error validation | 944 |
| MER-Prefer Test Stage 1 | Official test evaluation | 379 |
| MER-Prefer Test Stage 2 | Official test evaluation | 515 |

The error-augmented training set combines the original training preference pairs with accepted controlled negatives. The validation set contains the accepted controlled-error pairs used to report the four-error diagnostic results.

## Controlled Error Types

| Error type | Controlled modification |
|---|---|
| **Emotion Flip** | Changes the inferred emotion category or valence while preserving the cited multimodal evidence. |
| **Intensity Mismatch** | Changes only the degree of an emotion or cue while preserving its category. |
| **Evidence Contradiction** | Reverses one or more related observations from one modality while preserving the broader interpretation. |
| **Modality Omission** | Removes one self-contained evidence clause from one modality without adding new facts. |

## Construction Pipeline

Each controlled negative is produced by the following pipeline:

1. **Preferred anchor selection.** The human-preferred description is selected from the original preference pair and segmented into numbered sentences.
2. **Qwen3 edit planning.** Qwen3-30B-A3B-Instruct proposes a structured local edit for one requested error type, including the exact source phrase and replacement phrase.
3. **Programmatic construction.** Code applies only the proposed local replacement while freezing all non-target text.
4. **Rule-based validation.** The candidate must satisfy type-specific constraints as well as quotation, locality, length, sentence-count, and lexical-overlap checks.
5. **Independent Qwen3 verification.** A separate Qwen3 inference pass checks the observed error type, non-target preservation, fluency, and construction quality. Only accepted candidates enter the released dataset.

Generation and verification use `Qwen3-30B-A3B-Instruct-2507` with greedy decoding. The verifier does not receive the gold preference label.

## Paper Results

The table below reports representative paper results in weighted F1 (WAF, %). **Orig. Val** is the original 563-pair validation set. **4-Error Avg** macro-averages WAF across the four controlled-error subsets. **Swap Cons** measures whether a judge preserves the selected description identity after candidate order is reversed.

| Model | Training setting | Orig. Val | 4-Error Avg | Swap Cons |
|---|---|---:|---:|---:|
| MiniCPM-o-2.6-8B | S1 Zero-shot | 59.48 | 88.46 | 81.94 |
| MiniCPM-o-2.6-8B | S1 Error-Aug SFT+DPO | 63.27 | 92.40 | 87.46 |
| Qwen2.5-Omni-7B | S2 Zero-shot | 65.53 | 78.97 | 70.42 |
| Qwen2.5-Omni-7B | S2 Error-Aug SFT+DPO | 79.75 | 90.97 | 84.21 |
| Qwen3-Omni-30B-A3B-Instruct | S2 Zero-shot | 73.18 | 93.82 | 91.55 |
| **Qwen3-Omni-30B-A3B-Instruct** | **S2 Error-Aug SFT+DPO** | **79.04** | **95.82** | **94.13** |
| EAPO calibrated fusion | Judges 16+19+21 | **80.82** | 94.35 | 91.41 |

For Qwen3, error-augmented SFT followed by DPO obtains the strongest controlled-error performance:

| Emotion Flip | Intensity Mismatch | Evidence Contradiction | Modality Omission | 4-Error Avg |
|---:|---:|---:|---:|---:|
| 94.22 | 94.57 | 98.04 | 96.44 | **95.82** |

The full paper-aligned model comparisons are organized by backbone in [docs/RESULTS.md](docs/RESULTS.md).

## Data Files

```text
data/
├── train/
│   ├── controlled_negatives.jsonl
│   ├── controlled_negatives.csv
│   ├── preference_pairs.csv
│   └── preference_pairs_position_balanced.csv
├── validation/
├── examples/
└── schema.json
```

- `controlled_negatives.jsonl` is the canonical release with nested edit and verification metadata.
- `controlled_negatives.csv` provides a flattened version of the same records.
- `preference_pairs.csv` contains the pairwise preference format used by the paper pipeline.
- `preference_pairs_position_balanced.csv` contains both candidate orders for position-bias control.

## Loading the Dataset

```python
import json
from pathlib import Path

records = [
    json.loads(line)
    for line in Path("data/train/controlled_negatives.jsonl").open(encoding="utf-8")
]

print(records[0]["error_type"])
print(records[0]["preferred_description"])
print(records[0]["controlled_negative"])
```

## Reproducing Construction

Install the package:

```bash
python -m pip install -e .
```

Prepare a source CSV with `name`, `a1`, `a2`, and `preference` columns, then run:

```bash
INPUT_CSV=/path/to/source.csv \
SPLIT=validation \
MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507 \
bash scripts/run_pipeline.sh
```

Validate the released files with:

```bash
python scripts/validate_release.py
```

## Documentation

- [Construction methodology](docs/METHODOLOGY.md)
- [Prompt templates](docs/PROMPTS.md)
- [Paper-aligned experimental results](docs/RESULTS.md)
- [Reproducibility guide](docs/REPRODUCIBILITY.md)
- [Dataset card](DATASET_CARD.md)
- [Field schema](data/schema.json)

## License and Source Media

The code is released under the MIT License. Dataset-specific terms are described in [DATA_LICENSE.md](DATA_LICENSE.md). Source audio and video are not redistributed; sample IDs are retained only as join keys for users with lawful access to the source benchmark.
