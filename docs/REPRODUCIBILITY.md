# Reproducibility Guide

## Environment

- Python 3.10 or newer
- PyTorch 2.1 or newer
- Transformers 4.57 or newer
- Accelerate 0.30 or newer
- Sufficient GPU memory for Qwen3-30B-A3B-Instruct-2507

Install with:

```bash
python -m pip install -e .
```

## Input Format

The source CSV must contain:

| Field | Description |
|---|---|
| `name` | Stable sample identifier |
| `a1` | First candidate description |
| `a2` | Second candidate description |
| `preference` | `a1` or `a2` |

No media paths are required because generation and verification are text-only.

## Full Pipeline

```bash
INPUT_CSV=/path/to/source.csv \
SPLIT=validation \
MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507 \
OUT_ROOT=outputs/validation \
bash scripts/run_pipeline.sh
```

The script deliberately launches generation and verification as separate Python processes so that generator model memory is released before the independent verifier is loaded.

## Individual Stages

Generation and programmatic checks:

```bash
eapo-generate \
  --input_csv /path/to/source.csv \
  --split val \
  --output_dir outputs/validation/generated \
  --model Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --generator_family qwen3_text \
  --input_type text \
  --max_attempts 2 \
  --max_length_delta 60 \
  --max_source_words 60 \
  --min_lexical_jaccard 0.45 \
  --max_sentence_delta 1
```

Independent verification:

```bash
eapo-verify \
  --input_csv /path/to/source.csv \
  --split val \
  --candidate_dir outputs/validation/generated \
  --output_dir outputs/validation/verified \
  --model Qwen/Qwen3-30B-A3B-Instruct-2507
```

Public export:

```bash
eapo-export \
  --source_csv /path/to/source.csv \
  --verified_jsonl outputs/validation/verified/accepted_generations.jsonl \
  --split validation \
  --output_dir outputs/validation/release
```

## Determinism

Both Qwen3 stages use greedy decoding with `do_sample=False`. Exact output reproducibility can still depend on hardware, attention implementation, PyTorch/Transformers versions, and model revision. The deterministic code checks and accepted public records are provided to support auditability even when a regenerated plan differs.

## Output Policy

Internal generation output includes retry history and raw model responses for debugging. `eapo-export` removes those fields. Publish only the exported release directory unless raw traces are intentionally required for a separate audit release.
