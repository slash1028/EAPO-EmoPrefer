# Dataset Card for EAPO-EmoPrefer

## Dataset Description

EAPO-EmoPrefer contains verified, controlled negative emotion descriptions constructed from human-preferred multimodal emotion descriptions. Each negative differs from its preferred anchor through a constrained local edit designed to instantiate one predefined error type.

The release is intended for preference-judge training, controlled error analysis, robustness evaluation, and research on multimodal emotion-description reliability.

## Data Instances

Each JSONL instance contains:

- `sample_id`: media-independent join key inherited from the source split.
- `split`: `train` or `validation`.
- `error_type`: one of four controlled categories.
- `preferred_description`: the human-preferred anchor description.
- `controlled_negative`: the verified generated negative.
- `edit_plan`: the exact source phrase, replacement phrase, target modality, rationale, and construction source.
- `automatic_metrics`: word counts, length delta, sentence delta, lexical Jaccard, and sequence similarity.
- `verification`: observed type, target-error flag, non-target-preservation flag, fluency flag, ordinal quality score, pass flag, and verifier notes.

See `data/examples/samplenew3_00025873_emotion_flip.json` for a complete record.

## Curation Process

1. Select the human-preferred description from each binary preference pair.
2. Number its sentences and request one local edit plan per error type from Qwen3-30B-A3B-Instruct-2507.
3. Apply exact phrase replacement in code while freezing all non-target text.
4. Reject candidates that violate type-specific structure, quotation preservation, length, sentence-count, or lexical-overlap constraints.
5. Audit the remaining preferred-negative pairs with a separate text-only Qwen3 inference call.
6. Retain a candidate only when its observed type matches the requested type, the target error is present, non-target content is preserved, the text is fluent, and quality is at least 3/5.

The quality score is an ordinal verifier judgment, not a calibrated probability or confidence score.

## Dataset Statistics

Following the paper's reporting convention, EmoPrefer-Data-V2 contains 1,618 original training pairs, the EAPO error-augmented training set contains 4,526 pairs, EmoPrefer-Data contains 563 original validation pairs, and the controlled-error validation set contains 944 generated pairs. Detailed machine-readable counts are available in `data/*/statistics.json`.

## Intended Uses

- Training or evaluating preference judges for emotion descriptions.
- Measuring sensitivity to specific controlled error types.
- Studying position bias by constructing downstream candidate-order swaps.
- Auditing how multimodal judges use affective evidence.

## Out-of-Scope Uses

- Reconstructing or redistributing source media.
- Inferring real identities or sensitive personal attributes.
- Treating generated descriptions as factual annotations of people outside the benchmark context.
- Treating verifier quality scores as calibrated uncertainty estimates.

## Limitations

- Generation and verification are text-only and operate on descriptions rather than directly re-inspecting source media.
- The generator and verifier use the same Qwen3 checkpoint in separate inference calls, so their errors may be correlated.
- Type yields are uneven because candidates are retained independently and ambiguous edits are discarded.
- Local editing can leave residual discourse-level tension even when the selected span is valid.
- Automated verification does not replace human review for high-stakes use.
- Source descriptions and sample identifiers may remain governed by the original benchmark terms.

## Media and Privacy

No raw media is included. Sample identifiers are retained solely to support reproducibility for authorized benchmark users. Users are responsible for complying with the source dataset's access, privacy, and redistribution requirements.
