# EAPO-EmoPrefer

EAPO-EmoPrefer is a controlled error-augmented preference dataset for multimodal emotion-description evaluation. Starting from a human-preferred description, the pipeline constructs a minimal local error, applies deterministic structural checks, and uses a separate Qwen3 inference pass to verify the error type and construction quality.

This repository release contains the controlled data-construction pipeline and verified annotations only. It does **not** contain model-training code, model weights, raw audio, or raw video.

## Dataset Summary

| Split | Source samples | Samples with generated negatives | Controlled negatives | All four types |
|---|---:|---:|---:|---:|
| Train | 1,618 | 1,252 | 2,908 | 77 |
| Validation | 563 | 443 | 944 | 17 |
| **Total** | **2,181** | **1,695** | **3,852** | **94** |

| Error type | Train | Validation | Total |
|---|---:|---:|---:|
| Emotion Flip | 749 | 317 | 1,066 |
| Intensity Mismatch | 405 | 99 | 504 |
| Evidence Contradiction | 1,103 | 342 | 1,445 |
| Modality Omission | 651 | 186 | 837 |

Each canonical controlled-negative record stores one semantic preferred-negative relation. Candidate-order duplication is excluded from the canonical JSONL/CSV annotations; an optional position-balanced pair file is provided separately for exact experimental accounting.

To match the data accounting used in the paper, the repository exposes three explicit views:

| Data view | Train | Validation | Meaning |
|---|---:|---:|---|
| Controlled generated negatives | 2,908 | 944 | Four Qwen3-generated and independently Qwen3-verified error types |
| Five-type preference pairs | 4,526 | 1,507 | Controlled negatives plus one original rejected pair per source sample |
| Position-balanced pair rows | 9,052 | 3,014 | Both candidate orders for every five-type pair |

Use the first row when reporting the number of newly generated negatives, the second for the canonical five-type preference dataset, and the third for the position-balanced training representation.

## Controlled Error Types

- **Emotion Flip:** changes only the inferred emotion category or valence while preserving observed evidence.
- **Intensity Mismatch:** changes the degree of the same cue or emotion without changing its category.
- **Evidence Contradiction:** reverses one or more closely related observations in exactly one modality.
- **Modality Omission:** removes one self-contained evidence clause from exactly one modality without adding facts.

## Repository Layout

```text
EAPO-EmoPrefer/
├── data/
│   ├── train/
│   │   ├── controlled_negatives.jsonl
│   │   ├── controlled_negatives.csv
│   │   ├── preference_pairs.csv
│   │   ├── preference_pairs_position_balanced.csv
│   │   └── statistics.json
│   ├── validation/
│   ├── examples/
│   ├── statistics/          # Aggregate counts and quality summaries
│   └── schema.json
├── docs/
│   ├── METHODOLOGY.md
│   ├── PROMPTS.md
│   └── REPRODUCIBILITY.md
├── scripts/run_pipeline.sh
└── src/eapo_emoprefer/
```

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

The JSONL representation preserves nested edit-plan and verification metadata. The CSV representation provides the same core fields in a flattened form.

- `preference_pairs.csv` contains each original or controlled preferred-negative relation once.
- `preference_pairs_position_balanced.csv` contains both A1/A2 candidate orders and is the exact count used for position-balanced training rows.

## Reproducing Data Construction

Install the package:

```bash
python -m pip install -e .
```

Prepare a source CSV with these columns:

```text
name,a1,a2,preference
```

`preference` must be either `a1` or `a2`. The selected candidate becomes the preferred anchor. Then run:

```bash
INPUT_CSV=/path/to/source.csv \
SPLIT=validation \
MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507 \
bash scripts/run_pipeline.sh
```

The pipeline runs three processes sequentially:

1. Qwen3 proposes one structured local edit for each requested error type.
2. Deterministic code assembles the candidate and applies format, locality, quotation, length, and overlap checks.
3. A separately loaded Qwen3 verifier audits the preferred-negative pair and retains only candidates that pass all quality conditions.

Generation and verification use greedy decoding (`do_sample=False`). No audio or video is loaded by this text-only release pipeline.

Validate a downloaded or regenerated release with:

```bash
python scripts/validate_release.py
```

## Source Media

Media files are deliberately excluded. `sample_id` is retained only as a join key for users who have independently obtained lawful access to the source benchmark. This repository does not grant rights to any source audio, video, or third-party benchmark content.

## Documentation

- [Methodology](docs/METHODOLOGY.md)
- [Prompt templates](docs/PROMPTS.md)
- [Reproducibility guide](docs/REPRODUCIBILITY.md)
- [Paper data accounting](docs/PAPER_DATA_ACCOUNTING.md)
- [Dataset card](DATASET_CARD.md)
- [Field schema](data/schema.json)

## License

The code is released under the MIT License. Dataset-specific terms and source-media restrictions are described in [DATA_LICENSE.md](DATA_LICENSE.md). Maintainers should confirm compatibility with the source benchmark terms before making the repository public.
