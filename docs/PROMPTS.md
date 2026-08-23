# Prompt Templates

The exact executable templates are defined in `src/eapo_emoprefer/generate.py`. This document presents their human-readable structure.

## Edit-Planning Prompt

```text
Create exactly ONE local phrase-edit plan for controlled error type: {error_type}.
Do not return plans for any other type and do not rewrite the complete description.

Type definition:
{type_specific_instruction}

Numbered official preferred description:
{numbered_preferred_description}

Rules:
- Copy sentence_id and source_phrase exactly from one numbered sentence.
- source_phrase must occur exactly once.
- replacement_phrase must be a fluent local replacement.
- Text outside source_phrase is frozen.
- Keep literal dialogue/subtitle quotations character-for-character identical.
- Never alter people, events, chronology, or quoted content.
- Apply the type-specific locality and preservation constraints.

Return JSON only:
{"plans": [{type_specific_schema}]}
```

### Emotion Flip Instruction

```text
Edit only a high-level inferred emotion conclusion or valence phrase.
Do not edit observed gaze, face, voice, action, clothing, location,
background, event, quotation, or any concrete audio/visual cue.
```

### Intensity Mismatch Instruction

```text
Choose one explicit, gradable cue or inferred emotion phrase.
Keep the same emotion family and the same attribute or emotion word,
but change only degree or arousal.
```

### Evidence Contradiction Instruction

```text
Contradict one or more closely related observable cues within exactly
one modality. Preserve broad emotion, people, events, chronology,
quotations, and modality attribution.
```

### Modality Omission Instruction

```text
Delete one self-contained clause containing concrete emotional evidence
from exactly one modality. Add no filler or new facts. Preserve the global
emotion and every non-target fact.
```

## Independent Verification Prompt

```text
Independently classify intentionally worse descriptions for preference training.

The requested type is only a claim from another generator: do not assume it is correct.
You receive text only, so audit the local edit relation between the preferred
description and its negative. Do not infer unobserved video facts.

Official preferred description:
{preferred_description}

Requested type, source sentence, source phrase, replacement phrase,
and full negative:
{candidate_block}

Choose observed_type from emotion_flip, intensity_mismatch,
evidence_contradiction, modality_omission, or other.

Evaluate targeted_error_present, non_target_preserved, fluency,
and construction quality from 1 to 5.

Return JSON only:
{"assessments": [{assessment_schema}]}
```

The verifier's `quality_score` is an ordinal quality judgment. It is not a calibrated confidence or probability.
