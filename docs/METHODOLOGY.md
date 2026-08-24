# Controlled Negative Construction Methodology

## Overview

The pipeline separates proposal, deterministic construction, and semantic verification. Qwen3 never directly rewrites an unrestricted full description: it proposes a structured local edit, and code decides whether that plan can be safely assembled.

```text
Preferred description + requested error type
                    ↓
Qwen3 structured local edit plan
                    ↓
Exact replacement + programmatic validation
                    ↓
Independent Qwen3 pair verification
                    ↓
Verified controlled negative
```

## Stage 1: Preferred Anchor

For an input row containing `a1`, `a2`, and `preference`, the preferred candidate is selected as the anchor. The rejected candidate is not rewritten. The preferred description is segmented and numbered as `[S1]`, `[S2]`, and so forth so that a generated plan can identify one exact edit location.

## Stage 2: Structured Edit Planning

The text-only `Qwen3-30B-A3B-Instruct-2507` checkpoint receives the numbered preferred description and exactly one requested error type. It returns a JSON object containing:

- sentence identifier;
- exact source phrase;
- local replacement phrase;
- target modality or global inference level;
- type-specific preservation fields;
- short rationale.

The complete prompt templates are documented in `PROMPTS.md` and implemented in `generate.plan_prompt`.

## Stage 3: Deterministic Construction and Rules

The program locates the source phrase exactly once in the selected sentence and replaces only that span. Text outside the selected phrase is frozen.

Shared hard checks include:

- valid sentence identifier and unique source-phrase match;
- non-empty replacement except for modality omission;
- literal quotation preservation;
- valid target modality;
- bounded source-span and length differences;
- bounded full-description length and sentence-count differences;
- minimum lexical Jaccard overlap;
- candidate differs from both preferred and official rejected descriptions;
- generated error types do not collapse to duplicate text.

Type-specific checks include:

### Emotion Flip

- Target must be a high-level inferred emotion or valence phrase.
- Target level must be `global`.
- Before and after emotions must be distinct and grounded in their respective spans.
- Observed facial, vocal, behavioral, and contextual evidence may not be selected as the edit target.
- Intensity and evidence preservation fields must be true.

### Intensity Mismatch

- The same emotion family and observable attribute must be retained.
- Only degree or arousal changes.
- Changes such as fast speech to slow speech are rejected as evidence contradiction rather than intensity mismatch.

### Evidence Contradiction

- One to four closely related observable cues may be changed.
- All changed cues must belong to exactly one modality.
- Broad emotion, events, quotations, and modality attribution remain fixed.

### Modality Omission

- Replacement must be empty.
- The source must be a grammatically removable 5--30 word evidence clause.
- Embedded deletion spans must include their leading connector.
- At least one exact concrete cue must be removed.
- The edit cannot add facts or leave a dangling connective.

The published generation configuration uses a maximum full-text length delta of 60 words, minimum lexical Jaccard of 0.45, maximum sentence-count delta of 1, and at most two generation attempts per run.

## Stage 4: Independent Text Verification

Rule-valid candidates are sent to a separate Qwen3 process. The verifier receives the preferred description, requested type, source sentence, source phrase, replacement phrase, and full negative. It does not receive media or preference labels.

More precisely, the human label is used before generation to select the preferred anchor from `a1` and `a2`. The verifier subsequently sees that selected anchor but not the raw `preference=a1/a2` field or original candidate position. Its task is construction-quality auditing, not blind recovery of the original human preference.

The requested type is explicitly presented as an untrusted claim. The verifier independently predicts an observed type and evaluates:

- whether the targeted error is clear;
- whether non-target content is preserved;
- whether the candidate is fluent;
- construction quality on a 1--5 ordinal scale.

A candidate passes only when:

```text
observed_type == requested_type
and targeted_error_present
and non_target_preserved
and fluent
and quality_score >= 3
```

Rejected types are discarded independently. A source sample can therefore contribute any subset of the four generated types.

## Decoding Configuration

Both the edit-planning and semantic-verification calls set `do_sample=False`. With the default single beam, decoding greedily chooses the highest-scoring next token at every step; no temperature, top-k, or top-p sampling is applied. This reduces random variation between runs but does not guarantee bit-identical output across different model revisions, hardware, attention kernels, or library versions.

## Stage 5: Public Export

The public export stores each verified relation once. It removes raw model responses, retry histories, local file paths, and candidate-order duplication while preserving the final edit plan, automatic metrics, and verifier assessment.
