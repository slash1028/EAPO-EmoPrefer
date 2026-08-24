# Reproducibility Guide

## Upstream Data Access

1. Obtain the original preference annotations from the [EmoPrefer repository](https://github.com/zeroQiaoba/AffectGPT/tree/master/EmoPrefer).
2. Request access to [MER2025 on Hugging Face](https://huggingface.co/datasets/MERChallenge/MER2025), accept its EULA, provide the requested contact information, and wait for approval.
3. Download the authorized media according to `README_AFTER_APPROVAL.md` in the gated repository.
4. Keep the upstream media outside this repository. Join EAPO records to clips using `sample_id` only when multimodal training or evaluation is required.

The controlled-negative generation and verification stages are text-only and therefore do not require media paths. The complete multimodal preference-judge experiments do require authorized source media. See `DATA_ACCESS.md` for the relationship among the files.

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

Both text-only Qwen3 stages use greedy decoding with `do_sample=False`. With the default `num_beams=1`, each generation step selects the highest-scoring next token rather than randomly sampling. Temperature, top-k, and top-p do not control token selection in this mode. Exact output reproducibility can still depend on hardware, attention implementation, PyTorch/Transformers versions, and model revision. The deterministic code checks and accepted public records are provided to support auditability even when a regenerated plan differs.

## Output Policy

Internal generation output includes retry history and raw model responses for debugging. `eapo-export` removes those fields. Publish only the exported release directory unless raw traces are intentionally required for a separate audit release.
