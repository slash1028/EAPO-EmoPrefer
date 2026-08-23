#!/usr/bin/env bash
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${PYTHON:-python}
MODEL=${MODEL:-Qwen/Qwen3-30B-A3B-Instruct-2507}
INPUT_CSV=${INPUT_CSV:?Set INPUT_CSV to a CSV with name,a1,a2,preference columns}
SPLIT=${SPLIT:-validation}
OUT_ROOT=${OUT_ROOT:-$REPO/outputs/$SPLIT}
MAX_SAMPLES=${MAX_SAMPLES:-0}

case "$SPLIT" in
  train) INTERNAL_SPLIT=train ;;
  validation) INTERNAL_SPLIT=val ;;
  *) echo "SPLIT must be train or validation" >&2; exit 2 ;;
esac

export QWEN3_TEXT_ATTN_IMPL=${QWEN3_TEXT_ATTN_IMPL:-sdpa}
export QWEN3_TEXT_MAX_NEW_TOKENS=${QWEN3_TEXT_MAX_NEW_TOKENS:-420}
export QWEN3_TEXT_VERIFY_MAX_NEW_TOKENS=${QWEN3_TEXT_VERIFY_MAX_NEW_TOKENS:-480}

mkdir -p "$OUT_ROOT/generated" "$OUT_ROOT/verified" "$OUT_ROOT/release"

"$PYTHON" -m eapo_emoprefer.generate \
  --input_csv "$INPUT_CSV" \
  --split "$INTERNAL_SPLIT" \
  --output_dir "$OUT_ROOT/generated" \
  --model "$MODEL" \
  --generator_family qwen3_text \
  --input_type text \
  --max_samples "$MAX_SAMPLES" \
  --max_attempts 2 \
  --max_length_delta 60 \
  --max_source_words 60 \
  --min_lexical_jaccard 0.45 \
  --max_sentence_delta 1

"$PYTHON" -m eapo_emoprefer.verify \
  --input_csv "$INPUT_CSV" \
  --split "$INTERNAL_SPLIT" \
  --candidate_dir "$OUT_ROOT/generated" \
  --output_dir "$OUT_ROOT/verified" \
  --model "$MODEL" \
  --max_samples "$MAX_SAMPLES"

"$PYTHON" -m eapo_emoprefer.export_release \
  --source_csv "$INPUT_CSV" \
  --verified_jsonl "$OUT_ROOT/verified/accepted_generations.jsonl" \
  --split "$SPLIT" \
  --output_dir "$OUT_ROOT/release"

echo "Release data: $OUT_ROOT/release"
