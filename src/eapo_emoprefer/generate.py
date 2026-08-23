#!/usr/bin/env python3
"""Generate independently verified controlled-error negatives from local phrase edits."""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import dataset_utils as base
from .qwen3_text_backend import Qwen3TextAgent


VALID_MODALITIES = {"global", "visual", "audio", "text", "context"}

ERROR_TYPES = (
    "emotion_flip",
    "intensity_mismatch",
    "evidence_contradiction",
    "modality_omission",
)
base.ERROR_TYPES = ERROR_TYPES
base.ALL_TYPES = ("original_rejected",) + ERROR_TYPES
base.TYPE_ALIASES.update({
    "modality underspecification": "modality_omission",
    "modality_underspecification": "modality_omission",
    "modality omission": "modality_omission",
    "modality_omission": "modality_omission",
})


def parse_json_object_lenient(response: str) -> dict[str, Any]:
    """Decode the first JSON object and tolerate trailing model commentary/objects."""
    text = str(response or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\\s*", "", text, flags=re.I)
        text = re.sub(r"\\s*```.*$", "", text, flags=re.S)
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found")
    value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError("decoded JSON value is not an object")
    return value


def sentence_spans(text: str) -> list[tuple[int, int, str]]:
    """Return exact sentence offsets without asking the model to quote source text."""
    text = base.clean_text(text)
    spans: list[tuple[int, int, str]] = []
    start = 0
    for match in re.finditer(r'[.!?](?:["\u201d])?\s+(?=[A-Z])', text):
        boundary = match.group(0)
        end = match.start() + len(boundary.rstrip())
        spans.append((start, end, text[start:end]))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text), text[start:]))
    return [(left, right, sentence) for left, right, sentence in spans if sentence.strip()]


def numbered_description(text: str) -> str:
    return "\n".join(
        f"[S{index}] {sentence}"
        for index, (_, _, sentence) in enumerate(sentence_spans(text), 1)
    )


def parse_sentence_id(value: Any) -> int:
    """Accept both numeric ids and the prompt-native S3/[S3] notation."""
    try:
        return int(value)
    except (TypeError, ValueError):
        match = re.fullmatch(r"\s*\[?\s*[sS]\s*(\d+)\s*\]?\s*", str(value or ""))
        return int(match.group(1)) if match else 0


def edit_instruction(wrong_type: str) -> str:
    return {
        "emotion_flip": (
            "Edit only a high-level inferred emotion conclusion or valence phrase, such as 'this conveys unease'. "
            "Do not edit any observed gaze, face, voice, action, clothing, location, background, event, quotation, "
            "or concrete audio/visual cue."
        ),
        "intensity_mismatch": (
            "Choose one explicit, gradable cue or inferred emotion phrase. Keep the same emotion family and exactly "
            "the same attribute/emotion word, but change only degree or arousal. Prefer emotion-strength edits such "
            "as mild sadness -> intense sadness or slightly anxious -> extremely anxious; visual edits such as slight "
            "smile -> broad smile are also allowed. Do not change an action, event, modality, or emotion category."
        ),
        "evidence_contradiction": (
            "Contradict one or more closely related observable cues within exactly one modality. Preserve the broad "
            "emotion interpretation, people, events, chronology, quotations, and modality attribution."
        ),
        "modality_omission": (
            "Delete one self-contained clause containing concrete emotional evidence from exactly one modality "
            "(visual, audio, or text). Do not add generic filler. Preserve the global emotion and every non-target fact."
        ),
    }[wrong_type]


def plan_prompt(row: dict[str, str], requested_types: list[str], feedback: dict[str, list[str]]) -> str:
    if len(requested_types) != 1:
        raise ValueError(f"v11 requires exactly one requested type, got {requested_types}")
    preferred, _ = base.chosen_rejected(row)
    wrong_type = requested_types[0]
    feedback_lines = [f"- {error}" for error in feedback.get(wrong_type, [])]
    feedback_block = ""
    if feedback_lines:
        feedback_block = "\nPrevious failure(s) to correct:\n" + "\n".join(feedback_lines)
    schemas = {
        "emotion_flip": (
            '{"type":"emotion_flip","sentence_id":1,"source_phrase":"explicit emotion phrase",'
            '"replacement_phrase":"different emotion phrase","target_modality":"global",'
            '"emotion_before":"...","emotion_after":"...","intensity_preserved":true,'
            '"evidence_preserved":true,"rationale":"..."}'
        ),
        "intensity_mismatch": (
            '{"type":"intensity_mismatch","sentence_id":1,"source_phrase":"mild sadness",'
            '"replacement_phrase":"intense sadness","target_modality":"global",'
            '"target_attribute":"emotion","emotion_family":"sadness","intensity_before":"mild",'
            '"intensity_after":"intense","emotion_family_preserved":true,'
            '"same_attribute_preserved":true,"rationale":"..."}'
        ),
        "evidence_contradiction": (
            '{"type":"evidence_contradiction","sentence_id":1,"source_phrase":"voice is low and weak",'
            '"replacement_phrase":"voice is loud and strong","target_modality":"audio",'
            '"target_cues":["low","weak"],"changed_observation_count":2,'
            '"broad_emotion_preserved":true,"modality_attribution_preserved":true,"rationale":"..."}'
        ),
        "modality_omission": (
            '{"type":"modality_omission","sentence_id":1,'
            '"source_phrase":"while her voice remains quiet and hesitant",'
            '"replacement_phrase":"","target_modality":"audio",'
            '"specific_cues_removed":["quiet","hesitant"],'
            '"global_emotion_preserved":true,"no_new_facts":true,"rationale":"..."}'
        ),
    }
    return f"""Create exactly ONE local phrase-edit plan for controlled error type: {wrong_type}.
Do not return plans for any other type and do not rewrite the complete description.

Type definition:
{edit_instruction(wrong_type)}

Numbered official preferred description:
{numbered_description(preferred)}

Rules:
- Copy sentence_id and source_phrase exactly from one numbered sentence; source_phrase must occur exactly once.
- replacement_phrase must be a fluent local replacement, except for modality_omission where it must be an empty string.
  Text outside source_phrase is frozen.
- Keep literal dialogue/subtitle quotations character-for-character identical.
- Never alter people, events, chronology, or quoted content.
- emotion_flip: source_phrase must be the conclusion/inference phrase, not an observed cue. Scene, clothing, setting,
  actions, gaze, facial movements, vocal properties, and concrete evidence phrases are forbidden edit targets.
- intensity_mismatch: preserve the exact same attribute noun or emotion word and emotion family; change only degree.
  Prefer explicit weak/moderate/strong emotion wording (mild sadness -> intense sadness; slightly anxious -> extremely
  anxious). Do not turn fast speech into slow speech: that is an evidence contradiction, not an intensity mismatch.
- evidence_contradiction: edit related observations from one modality only; do not rewrite the global emotion conclusion.
- modality_omission: source_phrase must be a self-contained, grammatically removable clause of 5--30 words containing
  concrete evidence from one modality. For an embedded deletion, include its leading connector, for example 'while ...',
  'with ...', or 'as well as ...'; never delete only the noun phrase after a surviving connector. Copy each removed cue
  as an exact substring from source_phrase. replacement_phrase must be empty. The resulting sentence must remain fluent.
- Prefer short edits, but coherent evidence clauses may contain up to 30 words.{feedback_block}

Return JSON only:
{{"plans":[{schemas[wrong_type]}]}}"""
def clean_plan_value(value: Any) -> Any:
    if isinstance(value, str):
        return base.clean_text(value)
    if isinstance(value, list):
        return [base.clean_text(item) for item in value]
    return value


def parse_plans(response: str, requested_types: list[str]) -> dict[str, dict[str, Any]]:
    parsed = parse_json_object_lenient(response)
    items = parsed.get("plans")
    if not isinstance(items, list):
        raise ValueError("missing plans list")
    plans: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        wrong_type = base.normalize_type(str(item.get("type", "")))
        if wrong_type not in requested_types:
            continue
        if wrong_type in plans:
            raise ValueError(f"duplicate plan for {wrong_type}")
        plan = {key: clean_plan_value(value) for key, value in item.items()}
        plan["type"] = wrong_type
        plan["construction"] = "qwen3_generated"
        plans[wrong_type] = plan
    return plans


def bool_field(plan: dict[str, Any], field: str) -> bool:
    return plan.get(field) is True or str(plan.get(field, "")).lower() == "true"


def quoted_segments(text: str) -> list[str]:
    return [base.clean_text(value) for value in re.findall(r'["\u201c](.*?)["\u201d]', text)]


def cjk_chars(text: str) -> list[str]:
    return re.findall(r'[\u3400-\u9fff]', text)



def normalize_modality(value: Any) -> str:
    value = base.clean_text(value).lower()
    aliases = {
        "video": "visual", "vision": "visual", "image": "visual",
        "auditory": "audio", "vocal": "audio", "voice": "audio",
        "subtitle": "text", "transcript": "text", "language": "text",
    }
    return aliases.get(value, value)

EMOTION_TERMS = {
    "angry", "anger", "annoyed", "anxious", "calm", "cheerful", "confident", "confused",
    "contempt", "contemptuous", "curious", "detached", "disappointed", "disdainful", "distress",
    "fear", "fearful", "frustrated", "gentle", "happy", "hesitant", "indifferent", "irritated",
    "joy", "nervous", "neutral", "regret", "relieved", "respectful", "sad", "satisfied",
    "serious", "surprised", "tense", "uncertain", "uneasy", "upset", "worried",
}
EMOTION_FORBIDDEN_TARGETS = {
    "background", "clothing", "decor", "garden", "location", "office", "park", "room", "scene",
    "setting", "surroundings", "uniform", "weather",
}
INTENSITY_ATTRIBUTES = {
    "brow", "eyebrow", "eyes", "expression", "frown", "gaze", "intensity", "mouth", "pace",
    "pitch", "posture", "smile", "speech", "tone", "tension", "voice", "volume",
}
EMOTION_FLIP_OBSERVATION_TOKENS = {
    "audio", "brow", "eye", "eyes", "expression", "face", "facial", "frown", "gaze", "gesture",
    "look", "mouth", "posture", "smile", "sound", "speech", "tone", "video", "voice",
}
EMOTION_FLIP_INFERENCE_MARKERS = (
    "conclude", "conveys", "convey", "expressing", "expresses", "experience", "experiences",
    "implies", "indicates", "infer", "inferred", "interpret", "interpreted", "reflects", "reveals",
    "suggests", "suggesting", "attitude", "emotion", "emotional",
)
MODALITY_MARKERS = {
    "audio": ("audio", "voice", "vocal", "tone", "pace", "volume", "speech", "intonation", "pitch", "sound"),
    "visual": ("video", "visual", "face", "facial", "gaze", "eyes", "brow", "mouth", "posture", "hand", "gesture", "expression", "body language"),
    "text": ("text", "subtitle", "words", "statement", "dialogue", "transcript", "says", "quotation"),
    "context": ("scene", "setting", "background", "context", "environment"),
}

EMOTION_INTENSITY_NOUNS = (
    "anger|anxiety|curiosity|disappointment|excitement|frustration|happiness|joy|nervousness|regret|"
    "sadness|surprise|tension|unease"
)
EMOTION_INTENSITY_ADJECTIVES = (
    "angry|anxious|calm|confident|curious|disappointed|excited|fearful|frustrated|happy|nervous|"
    "regretful|relieved|sad|surprised|tense|uneasy"
)
EMOTION_INTENSITY_NOUN_SET = set(EMOTION_INTENSITY_NOUNS.split("|"))
EMOTION_INTENSITY_LABEL_SET = EMOTION_INTENSITY_NOUN_SET | set(EMOTION_INTENSITY_ADJECTIVES.split("|"))


def token_set(text: str) -> set[str]:
    return set(base.word_tokens(text))


def replace_phrase(
    preferred: str,
    sentence_id: int,
    source_phrase: str,
    replacement_phrase: str,
) -> tuple[str, str, str]:
    spans = sentence_spans(preferred)
    if not 1 <= sentence_id <= len(spans):
        raise ValueError(f"sentence_id {sentence_id} outside [1, {len(spans)}]")
    start, end, source_sentence = spans[sentence_id - 1]
    occurrences = source_sentence.count(source_phrase) if source_phrase else 0
    if occurrences != 1:
        raise ValueError(
            f"source_phrase must occur exactly once in selected sentence; found {occurrences} exact matches"
        )
    edited_sentence = source_sentence.replace(source_phrase, replacement_phrase, 1)
    candidate = preferred[:start] + edited_sentence + preferred[end:]
    if not replacement_phrase:
        # Omission plans must remove a complete evidence clause, but retain a
        # conservative punctuation cleanup for adjacent comma boundaries.
        candidate = re.sub(r",\s*,", ",", candidate)
        candidate = re.sub(r",\s*([.!?])", r"\1", candidate)
    candidate = re.sub(r"\s+([,.;:!?])", r"\1", candidate)
    candidate = re.sub(r"\s{2,}", " ", candidate).strip()
    return candidate, source_sentence, edited_sentence


def validate_plan(
    row: dict[str, str],
    wrong_type: str,
    plan: dict[str, Any],
    max_length_delta: int,
    max_source_words: int,
    min_lexical_jaccard: float,
    max_sentence_delta: int,
) -> tuple[list[str], str, dict[str, Any]]:
    preferred, rejected = base.chosen_rejected(row)
    errors: list[str] = []
    sentence_id = parse_sentence_id(plan.get("sentence_id", 0))
    source_phrase = base.clean_text(plan.get("source_phrase", ""))
    replacement_phrase = base.clean_text(plan.get("replacement_phrase", ""))
    modality = normalize_modality(plan.get("target_modality", ""))
    try:
        candidate, source_sentence, edited_sentence = replace_phrase(
            preferred, sentence_id, source_phrase, replacement_phrase
        )
    except ValueError as exc:
        errors.append(str(exc))
        candidate, source_sentence, edited_sentence = preferred, "", ""

    if not source_phrase:
        errors.append("source_phrase is empty")
    if not replacement_phrase and wrong_type != "modality_omission":
        errors.append("replacement_phrase is empty")
    if source_phrase.lower() == replacement_phrase.lower():
        errors.append("replacement_phrase is identical to source_phrase")
    type_phrase_limits = {
        "emotion_flip": 45,
        "intensity_mismatch": 36,
        "evidence_contradiction": 45,
        "modality_omission": 45,
    }
    phrase_limit = min(max_source_words, type_phrase_limits[wrong_type])
    if base.word_count(source_phrase) > phrase_limit:
        errors.append(f"source_phrase exceeds {phrase_limit} words")
    phrase_length_delta = base.word_count(replacement_phrase) - base.word_count(source_phrase)
    allowed_phrase_delta = 30 if wrong_type == "modality_omission" else 15
    if abs(phrase_length_delta) > allowed_phrase_delta:
        errors.append(f"phrase length delta {phrase_length_delta} exceeds +/-{allowed_phrase_delta} words")
    if source_sentence and quoted_segments(source_sentence) != quoted_segments(edited_sentence):
        errors.append("literal quoted speech/subtitle content was changed")
    source_cjk = set(cjk_chars(source_sentence))
    if any(char not in source_cjk for char in cjk_chars(edited_sentence)):
        errors.append("edit introduced new Chinese characters")
    if modality not in VALID_MODALITIES:
        errors.append(f"invalid target_modality: {modality or '<empty>'}")
    if wrong_type == "emotion_flip" and modality != "global":
        errors.append("target_modality must be global for emotion_flip")
    if wrong_type in {"evidence_contradiction", "modality_omission"} and modality not in {"visual", "audio", "text", "context"}:
        errors.append(f"target_modality must identify a concrete modality for {wrong_type}")

    if wrong_type == "emotion_flip":
        before = base.clean_text(plan.get("emotion_before", ""))
        after = base.clean_text(plan.get("emotion_after", ""))
        if not before or not after or before.lower() == after.lower():
            errors.append("emotion_before and emotion_after must be distinct and non-empty")
        if not bool_field(plan, "intensity_preserved"):
            errors.append("intensity_preserved must be true")
        if not bool_field(plan, "evidence_preserved"):
            errors.append("evidence_preserved must be true")
        source_tokens = token_set(source_phrase)
        before_tokens = set(base.word_tokens(before))
        after_tokens = set(base.word_tokens(after))
        if not (source_tokens & (EMOTION_TERMS | EMOTION_INTENSITY_LABEL_SET)) and not before_tokens.intersection(source_tokens):
            errors.append("emotion_flip source_phrase lacks a grounded emotion conclusion")
        if before_tokens and not before_tokens.intersection(source_tokens):
            errors.append("emotion_before is not grounded in source_phrase")
        if after_tokens and not after_tokens.intersection(token_set(replacement_phrase)):
            errors.append("emotion_after is not grounded in replacement_phrase")
        if source_tokens & EMOTION_FORBIDDEN_TARGETS:
            errors.append("emotion_flip may not edit scene, setting, clothing, or background facts")
        lowered_source = source_phrase.lower()
        if not any(marker in lowered_source for marker in EMOTION_FLIP_INFERENCE_MARKERS):
            errors.append("emotion_flip must edit an inferred conclusion, not an observed cue")
    elif wrong_type == "intensity_mismatch":
        before = base.clean_text(plan.get("intensity_before", ""))
        after = base.clean_text(plan.get("intensity_after", ""))
        attribute = base.clean_text(plan.get("target_attribute", "")).lower()
        if not base.clean_text(plan.get("emotion_family", "")):
            errors.append("emotion_family is required")
        if not attribute:
            errors.append("target_attribute is required")
        if not before or not after or before.lower() == after.lower():
            errors.append("intensity_before and intensity_after must be distinct and non-empty")
        if not bool_field(plan, "emotion_family_preserved"):
            errors.append("emotion_family_preserved must be true")
        if not bool_field(plan, "same_attribute_preserved"):
            errors.append("same_attribute_preserved must be true")
        shared_attributes = token_set(source_phrase) & token_set(replacement_phrase) & INTENSITY_ATTRIBUTES
        shared_emotions = (
            token_set(source_phrase) & token_set(replacement_phrase)
            & (EMOTION_TERMS | EMOTION_INTENSITY_LABEL_SET)
        )
        emotional_degree_edit = attribute in {"emotion", "affect", "emotion_label"} and bool(shared_emotions)
        if not shared_attributes and not emotional_degree_edit:
            errors.append("intensity_mismatch must preserve the same observable attribute")
        attribute_tokens = base.word_tokens(attribute)
        if attribute in {"emotion", "affect", "emotion_label"}:
            if not shared_emotions:
                errors.append("emotion intensity edit must preserve the same emotion word")
        elif attribute_tokens and not any(
            token in source_phrase.lower() and token in replacement_phrase.lower()
            for token in attribute_tokens
        ):
            errors.append("target_attribute is not preserved in both source and replacement")
        if before and not any(token in source_phrase.lower() for token in base.word_tokens(before)):
            errors.append("intensity_before is not grounded in source_phrase")
        if after and not any(token in replacement_phrase.lower() for token in base.word_tokens(after)):
            errors.append("intensity_after is not grounded in replacement_phrase")
    elif wrong_type == "evidence_contradiction":
        cues = plan.get("target_cues", [])
        if isinstance(cues, str):
            cues = [cues]
        cues = [base.clean_text(cue) for cue in cues if base.clean_text(cue)]
        if not cues:
            errors.append("target_cues must list at least one changed observable cue")
        try:
            changed_count = int(plan.get("changed_observation_count", 0))
        except (TypeError, ValueError):
            changed_count = 0
        if changed_count < 1 or changed_count > 4:
            errors.append("changed_observation_count must be between 1 and 4")
        if cues and changed_count != len(cues):
            errors.append("changed_observation_count must match target_cues")
        if not bool_field(plan, "broad_emotion_preserved"):
            errors.append("broad_emotion_preserved must be true")
        if not bool_field(plan, "modality_attribution_preserved"):
            errors.append("modality_attribution_preserved must be true")
    elif wrong_type == "modality_omission":
        cues = plan.get("specific_cues_removed", [])
        if not isinstance(cues, list) or not cues:
            errors.append("specific_cues_removed must list at least one concrete cue")
            cues = []
        cues = [base.clean_text(cue) for cue in cues if base.clean_text(cue)]
        exact_removed = 0
        for cue in cues:
            if cue.lower() not in source_phrase.lower():
                errors.append(f"declared removed cue is not in source_phrase: {cue}")
            elif cue.lower() in replacement_phrase.lower():
                errors.append(f"removed cue remains in replacement_phrase: {cue}")
            else:
                exact_removed += 1
        if exact_removed < 1:
            errors.append("modality edit must remove at least one exact concrete cue")
        if not bool_field(plan, "global_emotion_preserved"):
            errors.append("global_emotion_preserved must be true")
        if not bool_field(plan, "no_new_facts"):
            errors.append("no_new_facts must be true")
        if replacement_phrase:
            errors.append("modality_omission must delete the selected evidence clause")
        if base.word_count(source_phrase) < 5:
            errors.append("modality_omission source_phrase is too short to remove meaningful evidence")
        lowered_sentence = source_sentence.lower()
        if modality in MODALITY_MARKERS and not any(marker in lowered_sentence for marker in MODALITY_MARKERS[modality]):
            errors.append(f"selected sentence lacks recognizable {modality} evidence")
        if len(token_set(source_phrase)) < 3:
            errors.append("modality omission removes too little concrete information")
        source_at_start = source_sentence.strip().rstrip(".!?") == source_phrase.strip().rstrip(".!?")
        connector = re.match(
            r"^(?:while|as well as|because|given|based on|considering|with|including)\b",
            source_phrase.strip(), flags=re.IGNORECASE,
        )
        if not source_at_start and not connector:
            errors.append("embedded modality omission must include its leading connector")
        if re.search(r"\b(?:and|or|as well as|but|while)\s*[,.;!?]", edited_sentence, flags=re.IGNORECASE):
            errors.append("modality omission leaves a dangling connective")

    preferred_words = base.word_count(preferred)
    candidate_words = base.word_count(candidate)
    length_delta = candidate_words - preferred_words
    sentence_delta = abs(base.sentence_count(candidate) - base.sentence_count(preferred))
    jaccard = base.lexical_jaccard(preferred, candidate)
    similarity = base.sequence_similarity(preferred, candidate)
    if abs(length_delta) > max_length_delta:
        errors.append(f"assembled length delta {length_delta} exceeds +/-{max_length_delta} words")
    if sentence_delta > max_sentence_delta:
        errors.append(f"sentence-count delta {sentence_delta} exceeds {max_sentence_delta}")
    if jaccard < min_lexical_jaccard:
        errors.append(f"lexical overlap {jaccard:.3f} below {min_lexical_jaccard:.3f}")
    if candidate.lower() == preferred.lower():
        errors.append("assembled text is identical to preferred description")
    if candidate.lower() == rejected.lower():
        errors.append("assembled text copies the official rejected description")

    metrics = {
        "preferred_words": preferred_words,
        "negative_words": candidate_words,
        "length_delta": length_delta,
        "source_words": base.word_count(source_phrase),
        "replacement_words": base.word_count(replacement_phrase),
        "phrase_length_delta": phrase_length_delta,
        "sentence_delta": sentence_delta,
        "lexical_jaccard": jaccard,
        "sequence_similarity": similarity,
        "target_modality": modality,
        "sentence_id": sentence_id,
        "source_sentence": source_sentence,
        "edited_sentence": edited_sentence,
        "source_phrase": source_phrase,
        "replacement_phrase": replacement_phrase,
    }
    return errors, candidate, metrics
def load_partial(path: Path) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return states
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if record.get("name") and isinstance(record.get("plans"), dict):
                states[str(record["name"])] = record
    return states


def load_failed_feedback(path: Path) -> dict[str, dict[str, list[str]]]:
    """Recover the latest deterministic validation feedback for a resumable retry."""
    feedback_by_name: dict[str, dict[str, list[str]]] = {}
    if not path.exists():
        return feedback_by_name
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            name = str(record.get("name", ""))
            raw_feedback = record.get("feedback", {})
            if not name or not isinstance(raw_feedback, dict):
                continue
            cleaned: dict[str, list[str]] = {}
            for wrong_type in ERROR_TYPES:
                values = raw_feedback.get(wrong_type, [])
                if isinstance(values, list):
                    cleaned[wrong_type] = [base.clean_text(value) for value in values if base.clean_text(value)][-4:]
            feedback_by_name[name] = cleaned
    return feedback_by_name


def remove_previous_outputs(output_dir: Path) -> None:
    for name in (
        "generation_attempts.jsonl", "partial_generations.jsonl", "accepted_generations.jsonl",
        "failed_samples.jsonl", "pairs_5type_no_swap.csv", "pairs_5type_swap.csv",
        "pairs_error_aug_no_swap.csv", "pairs_error_aug_swap.csv",
        "quality_audit_all.csv", "manual_review_queue.csv", "quality_report.json", "manifest.json",
    ):
        path = output_dir / name
        if path.exists():
            path.unlink()


def duplicate_types(candidates: dict[str, str]) -> set[str]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for wrong_type, text in candidates.items():
        grouped[base.clean_text(text).lower()].append(wrong_type)
    return {wrong_type for types in grouped.values() if len(types) > 1 for wrong_type in types}



class Qwen3TextGenerator:
    """Adapter exposing deterministic Qwen3 text generation through the pipeline interface."""

    def __init__(self, model_root: str):
        max_new_tokens = int(os.environ.get("QWEN3_TEXT_MAX_NEW_TOKENS", "900"))
        attn = os.environ.get("QWEN3_TEXT_ATTN_IMPL", "sdpa")
        print(
            f"[generator] loading text-only Qwen3: {model_root} "
            f"attn={attn} max_new_tokens={max_new_tokens}",
            flush=True,
        )
        self.agent = Qwen3TextAgent(model_root, max_new_tokens, attn)

    def generate_message(
        self, audio_path: str, video_path: str, prompt: str, input_type: str
    ) -> str:
        del audio_path, video_path, input_type
        return prompt

    def func_calling(self, whole_messages: list[Any], temperature: Any = None,
                     batch_size: int = 1, names: list[str] | None = None) -> list[str]:
        del temperature
        names = names or [str(index) for index in range(len(whole_messages))]
        responses: list[str] = []
        for start in range(0, len(whole_messages), max(1, batch_size)):
            batch_messages = whole_messages[start:start + max(1, batch_size)]
            batch_names = names[start:start + max(1, batch_size)]
            print(f"[qwen3-text] batch names={batch_names}", flush=True)
            responses.extend(self.agent.generate_batch([str(prompt) for prompt in batch_messages]))
        return responses


def load_generator(model_root: str, family: str, tool_dir: Path) -> Any:
    del family, tool_dir
    return Qwen3TextGenerator(model_root)


VERIFIER_TYPES = set(ERROR_TYPES) | {"other"}


def corrected_verifier_prompt(
    row: dict[str, str],
    candidates: dict[str, dict[str, str]],
    plans: dict[str, dict[str, Any]],
) -> str:
    preferred, _ = base.chosen_rejected(row)
    spans = sentence_spans(preferred)
    blocks: list[str] = []
    schemas: list[str] = []
    for wrong_type, candidate in candidates.items():
        plan = plans[wrong_type]
        sentence_id = parse_sentence_id(plan.get("sentence_id", 0))
        source = spans[sentence_id - 1][2] if 1 <= sentence_id <= len(spans) else "<invalid>"
        blocks.append(
            f"REQUESTED TYPE (claim to audit): {wrong_type}\n"
            f"SOURCE SENTENCE: {source}\n"
            f"SOURCE PHRASE: {plan.get('source_phrase', '')}\n"
            f"REPLACEMENT PHRASE: {plan.get('replacement_phrase', '')}\n"
            f"FULL NEGATIVE: {candidate['text']}"
        )
        schemas.append(
            f'{{"requested_type":"{wrong_type}","observed_type":"other",'
            '"targeted_error_present":false,"non_target_preserved":false,'
            '"fluent":false,"quality_score":1,"notes":"..."}'
        )
    joined = "\n\n".join(blocks)
    schema = ",".join(schemas)
    return f"""Independently classify intentionally worse descriptions for preference training.
The requested type is only a claim from another generator: do not assume it is correct. You receive text only, so audit
the local edit relation between the preferred description and its negative. Do not infer unobserved video facts. Judge
whether the negative is a well-constructed example of the requested error category.

Official preferred description:
{preferred}

Candidates:
{joined}

Choose observed_type from emotion_flip, intensity_mismatch, evidence_contradiction,
modality_omission, or other:
- emotion_flip: only an inferred emotion category or valence changes; observed cues and their intensity remain fixed.
- intensity_mismatch: only the degree of the same cue or the same emotion word changes, such as slight smile -> broad
  smile or mild sadness -> intense sadness. A change from rapid speech to slow speech is evidence contradiction, not
  intensity mismatch, because it reverses a concrete observation.
- evidence_contradiction: one or more concrete observations in one modality directly contradict the preferred text, while broad emotion,
  events, quotations, and other modalities remain fixed.
- modality_omission: a concrete evidence clause from one modality is deleted, making the claim less grounded while the
  global emotion and all other facts remain fixed. Generic filler is not an omission.
- other: harmless paraphrase, supported correction, category leakage, multiple unrelated changes, or no clear error.

targeted_error_present asks whether the intended local degradation is clear from the two descriptions. non_target_preserved
asks whether unrelated people, events, quotations, modalities, and cues are unchanged. quality_score evaluates construction
quality rather than factual correctness: score 4--5 for a fluent, local, unambiguous training negative; 3 for usable with a
minor weakness; 1--2 for unusable.

Return JSON only:
{{"assessments":[{schema}]}}"""


def parse_corrected_verification(
    response: str,
    expected_types: list[str],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    parsed = parse_json_object_lenient(response)
    items = parsed.get("assessments")
    if not isinstance(items, list):
        raise ValueError("missing assessments list")
    assessments: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        wrong_type = base.normalize_type(str(item.get("requested_type", item.get("type", ""))))
        if wrong_type not in expected_types:
            continue
        predicted_type = base.normalize_type(
            str(item.get("observed_type", item.get("predicted_type", "other")))
        )
        if predicted_type not in VERIFIER_TYPES:
            predicted_type = "other"
        targeted_error_present = item.get("targeted_error_present") is True or str(
            item.get("targeted_error_present", "")
        ).lower() == "true"
        non_target_preserved = item.get("non_target_preserved") is True or str(
            item.get("non_target_preserved", "")
        ).lower() == "true"
        fluent = item.get("fluent") is True or str(item.get("fluent", "")).lower() == "true"
        try:
            quality_score = int(float(item.get("quality_score", 0)))
        except (TypeError, ValueError):
            quality_score = 0
        passed = (
            predicted_type == wrong_type
            and targeted_error_present
            and non_target_preserved
            and fluent
            and quality_score >= 3
        )
        assessments[wrong_type] = {
            "predicted_type": predicted_type,
            "targeted_error_present": targeted_error_present,
            "non_target_preserved": non_target_preserved,
            "fluent": fluent,
            "quality_score": quality_score,
            "pass": passed,
            "notes": base.clean_text(item.get("notes", "")),
        }
    errors: list[str] = []
    for wrong_type in expected_types:
        assessment = assessments.get(wrong_type)
        if assessment is None:
            errors.append(f"{wrong_type}: type-specific verifier omitted this type")
            continue
        if not assessment["pass"]:
            errors.append(
                f"{wrong_type}: independent verifier rejected "
                f"predicted={assessment['predicted_type']} targeted={assessment['targeted_error_present']} "
                f"non_target_preserved={assessment['non_target_preserved']} fluent={assessment['fluent']} "
                f"quality={assessment['quality_score']}: {assessment['notes']}"
            )
    return errors, assessments


def build_partial_outputs(
    rows: list[dict[str, str]],
    accepted: dict[str, dict[str, Any]],
    output_dir: Path,
    manual_review_samples: int,
    print_report: bool = True,
) -> dict[str, Any]:
    """Write every independently verified type while preserving the existing pair schema."""
    base_pairs: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    per_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    samples_with_any = 0
    samples_with_all = 0

    for row in rows:
        name = row["name"]
        preferred, rejected = base.chosen_rejected(row)
        original_metrics = {
            "preferred_words": base.word_count(preferred),
            "negative_words": base.word_count(rejected),
            "length_delta": base.word_count(rejected) - base.word_count(preferred),
            "sentence_delta": abs(base.sentence_count(rejected) - base.sentence_count(preferred)),
            "lexical_jaccard": base.lexical_jaccard(preferred, rejected),
            "sequence_similarity": base.sequence_similarity(preferred, rejected),
        }
        base_pairs.append(base.make_pair(
            name, preferred, rejected, "original_rejected", original_metrics, False
        ))
        per_type["original_rejected"].append(original_metrics)

        record = accepted.get(name)
        if not record:
            continue
        parsed = record.get("parsed", {})
        metrics_by_type = record.get("metrics", {})
        verification = record.get("verification", {})
        retained = [wrong_type for wrong_type in ERROR_TYPES if wrong_type in parsed]
        samples_with_any += int(bool(retained))
        samples_with_all += int(len(retained) == len(ERROR_TYPES))
        for wrong_type in retained:
            negative = parsed[wrong_type]["text"]
            metrics = metrics_by_type[wrong_type]
            base_pairs.append(base.make_pair(
                name, preferred, negative, wrong_type, metrics, False
            ))
            per_type[wrong_type].append(metrics)
            audit_rows.append({
                "name": name,
                "wrong_type": wrong_type,
                "preferred": preferred,
                "negative": negative,
                "official_rejected": rejected,
                **metrics,
                "semantic_verifier_pass": verification.get(wrong_type, {}).get("pass", ""),
                "semantic_verifier_notes": verification.get(wrong_type, {}).get("notes", ""),
            })

    base_pairs.sort(key=lambda item: (item["name"], item["wrong_type"]))
    swap_pairs: list[dict[str, Any]] = []
    for item in base_pairs:
        swap_pairs.append(item)
        swapped = dict(item)
        swapped["pair_id"] = item["pair_id"].replace("::base", "::swap")
        swapped["a1"], swapped["a2"] = item["a2"], item["a1"]
        swapped["preference"] = "a2" if item["preference"] == "a1" else "a1"
        swapped["is_swapped"] = "1"
        swap_pairs.append(swapped)

    for filename, values in (
        ("pairs_error_aug_no_swap.csv", base_pairs),
        ("pairs_5type_no_swap.csv", base_pairs),
        ("pairs_error_aug_swap.csv", swap_pairs),
        ("pairs_5type_swap.csv", swap_pairs),
    ):
        base.write_rows(output_dir / filename, values, base.PAIR_FIELDS)
    base.write_rows(output_dir / "quality_audit_all.csv", audit_rows, base.AUDIT_FIELDS)
    review_names = sorted({row["name"] for row in audit_rows})[:manual_review_samples]
    base.write_rows(
        output_dir / "manual_review_queue.csv",
        [row for row in audit_rows if row["name"] in set(review_names)],
        base.AUDIT_FIELDS,
    )

    type_report: dict[str, Any] = {}
    for wrong_type in base.ALL_TYPES:
        values = per_type.get(wrong_type, [])
        type_report[wrong_type] = {
            "pairs": len(values),
            "yield_percent": 100.0 * len(values) / len(rows) if rows else 0.0,
            "preferred_words_mean": statistics.fmean(item["preferred_words"] for item in values) if values else None,
            "negative_words_mean": statistics.fmean(item["negative_words"] for item in values) if values else None,
            "absolute_length_delta_mean": statistics.fmean(abs(item["length_delta"]) for item in values) if values else None,
            "lexical_jaccard_mean": statistics.fmean(item["lexical_jaccard"] for item in values) if values else None,
            "sequence_similarity_mean": statistics.fmean(item["sequence_similarity"] for item in values) if values else None,
        }
    report = {
        "official_binary_samples": len(rows),
        "samples_with_any_verified_generated_type": samples_with_any,
        "samples_with_all_four_verified_generated_types": samples_with_all,
        "generated_type_pairs": sum(len(per_type.get(wrong_type, [])) for wrong_type in ERROR_TYPES),
        "possible_generated_type_pairs": len(rows) * len(ERROR_TYPES),
        "generated_type_yield_percent": (
            100.0 * sum(len(per_type.get(wrong_type, [])) for wrong_type in ERROR_TYPES)
            / (len(rows) * len(ERROR_TYPES)) if rows else 0.0
        ),
        "no_swap_pair_rows": len(base_pairs),
        "swap_pair_rows": len(swap_pairs),
        "type_statistics": type_report,
    }
    (output_dir / "quality_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if print_report:
        print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return report

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input_csv", required=True)
    parser.add_argument("--split", required=True, choices=["train", "val"])
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--data_root", default=".", help="Compatibility argument; media are not loaded.")
    parser.add_argument("--tool_dir", default=".", help=argparse.SUPPRESS)
    parser.add_argument("--model", default="Qwen/Qwen3-30B-A3B-Instruct-2507")
    parser.add_argument("--generator_family", choices=["qwen3_text"], default="qwen3_text")
    parser.add_argument("--input_type", default="text", choices=["text"])
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--generation_batch_size", type=int, default=8)
    parser.add_argument("--max_samples", type=int, default=0)
    parser.add_argument("--max_attempts", type=int, default=3)
    parser.add_argument("--max_length_delta", type=int, default=40)
    parser.add_argument("--max_source_words", type=int, default=40)
    parser.add_argument("--min_lexical_jaccard", type=float, default=0.45)
    parser.add_argument("--max_sentence_delta", type=int, default=1)
    parser.add_argument("--manual_review_samples", type=int, default=50)
    parser.add_argument("--prepare_only", action="store_true", default=False)
    parser.add_argument("--force", action="store_true", default=False)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.force:
        remove_previous_outputs(output_dir)

    attempts_path = output_dir / "generation_attempts.jsonl"
    partial_path = output_dir / "partial_generations.jsonl"
    accepted_path = output_dir / "accepted_generations.jsonl"
    failed_path = output_dir / "failed_samples.jsonl"
    rows = [
        row for row in base.read_rows(Path(args.input_csv))
        if base.normalize_label(row.get("preference", "")) in {"a1", "a2"}
    ]
    if args.max_samples > 0:
        rows = rows[: args.max_samples]

    accepted = base.load_accepted(accepted_path)
    partial = load_partial(partial_path)
    prior_feedback = load_failed_feedback(failed_path)
    missing = [
        row for row in rows
        if row.get("name") and len(accepted.get(row["name"], {}).get("parsed", {})) < len(ERROR_TYPES)
    ]
    started = time.time()
    generated_calls = 0

    if missing and not args.prepare_only:
        model = load_generator(args.model, args.generator_family, Path(args.tool_dir))
        for batch_start in range(0, len(missing), max(1, args.batch_size)):
            batch_rows = missing[batch_start: batch_start + max(1, args.batch_size)]
            states: list[dict[str, Any]] = []
            for row in batch_rows:
                prior = partial.get(row["name"], accepted.get(row["name"], {}))
                state = {
                    "row": row,
                    "plans": dict(prior.get("plans", {})),
                    "parsed": dict(prior.get("parsed", {})),
                    "metrics": dict(prior.get("metrics", {})),
                    "feedback": {
                        wrong_type: list(prior_feedback.get(row["name"], {}).get(wrong_type, []))
                        for wrong_type in base.ERROR_TYPES
                    },
                    "verification": dict(prior.get("verification", {})),
                }
                states.append(state)

            for attempt in range(1, args.max_attempts + 1):
                active = [state for state in states if len(state["parsed"]) < len(base.ERROR_TYPES)]
                if not active:
                    break
                jobs = [
                    (state, wrong_type)
                    for state in active
                    for wrong_type in base.ERROR_TYPES
                    if wrong_type not in state["parsed"]
                ]
                print(
                    f"[attempt] split={args.split} batch={batch_start // max(1, args.batch_size) + 1} "
                    f"samples={len(active)} attempt={attempt}/{args.max_attempts} "
                    f"requests={len(jobs)}",
                    flush=True,
                )
                messages = [
                    base.model_messages(
                        model, state["row"], plan_prompt(state["row"], [wrong_type], state["feedback"]),
                        Path(args.data_root), args.input_type,
                    )
                    for state, wrong_type in jobs
                ]
                names = [
                    f"{state['row']['name']}:{wrong_type}:plan{attempt}"
                    for state, wrong_type in jobs
                ]
                call_started = time.time()
                responses = model.func_calling(
                    messages, batch_size=max(1, args.generation_batch_size), names=names
                )
                if len(responses) != len(jobs):
                    raise RuntimeError(
                        f"generator returned {len(responses)} responses for {len(jobs)} requests"
                    )
                generated_calls += len(messages)
                call_seconds = time.time() - call_started

                work: dict[int, dict[str, Any]] = {
                    id(state): {
                        "state": state,
                        "requested": [
                            wrong_type for wrong_type in base.ERROR_TYPES
                            if wrong_type not in state["parsed"]
                        ],
                        "responses": {},
                        "parsed_plans": {},
                        "errors_by_type": {
                            wrong_type: [] for wrong_type in base.ERROR_TYPES
                            if wrong_type not in state["parsed"]
                        },
                        "provisional": {},
                    }
                    for state in active
                }
                for (state, wrong_type), response in zip(jobs, responses):
                    row = state["row"]
                    item = work[id(state)]
                    item["responses"][wrong_type] = response
                    try:
                        parsed = parse_plans(response, [wrong_type])
                    except Exception as exc:  # noqa: BLE001
                        item["errors_by_type"][wrong_type].append(f"parse/structure failure: {exc}")
                        continue
                    if wrong_type not in parsed:
                        item["errors_by_type"][wrong_type].append("generation omitted this requested type")
                        continue
                    plan = parsed[wrong_type]
                    item["parsed_plans"][wrong_type] = plan
                    errors, candidate, metrics = validate_plan(
                        row, wrong_type, plan, args.max_length_delta, args.max_source_words,
                        args.min_lexical_jaccard, args.max_sentence_delta,
                    )
                    item["errors_by_type"][wrong_type].extend(errors)
                    if not errors:
                        item["provisional"][wrong_type] = {
                            "plan": plan,
                            "candidate": {
                                "type": wrong_type,
                                "text": candidate,
                                "changed_span": plan["replacement_phrase"],
                            },
                            "metrics": metrics,
                        }

                for item in work.values():
                    state = item["state"]
                    row = state["row"]
                    requested = item["requested"]
                    parsed_plans = item["parsed_plans"]
                    errors_by_type = item["errors_by_type"]
                    provisional = item["provisional"]
                    newly_valid: list[str] = []

                    verification_response = ""
                    verification_results: dict[str, dict[str, Any]] = {}

                    for wrong_type, candidate_item in provisional.items():
                        if errors_by_type[wrong_type]:
                            continue
                        state["plans"][wrong_type] = candidate_item["plan"]
                        state["parsed"][wrong_type] = candidate_item["candidate"]
                        state["metrics"][wrong_type] = candidate_item["metrics"]
                        state["verification"][wrong_type] = verification_results.get(
                            wrong_type,
                            {"pass": True, "notes": "awaiting independent Qwen3 verification"},
                        )
                        newly_valid.append(wrong_type)

                    duplicates = duplicate_types({k: v["text"] for k, v in state["parsed"].items()})
                    for wrong_type in duplicates:
                        state["plans"].pop(wrong_type, None)
                        state["parsed"].pop(wrong_type, None)
                        state["metrics"].pop(wrong_type, None)
                        state["verification"].pop(wrong_type, None)
                        errors_by_type.setdefault(wrong_type, []).append("assembled text duplicates another error type")
                        if wrong_type in newly_valid:
                            newly_valid.remove(wrong_type)

                    for wrong_type in base.ERROR_TYPES:
                        state["feedback"][wrong_type] = errors_by_type.get(wrong_type, [])[-4:]
                    base.append_jsonl(
                        attempts_path,
                        {
                            "name": row["name"], "split": args.split, "attempt": attempt,
                            "requested_types": requested, "raw_responses": item["responses"],
                            "parsed_plans": parsed_plans, "errors_by_type": errors_by_type,
                            "verification_response": verification_response,
                            "verification": verification_results,
                            "newly_valid_types": newly_valid,
                            "retained_types": sorted(state["parsed"]), "call_seconds": call_seconds,
                        },
                    )
                    print(
                        f"[plan] name={row['name']} valid={newly_valid} "
                        f"retained={sorted(state['parsed'])} missing="
                        f"{[t for t in base.ERROR_TYPES if t not in state['parsed']]} "
                        f"call_sec={call_seconds:.1f}",
                        flush=True,
                    )

            for state in states:
                row = state["row"]
                partial_record = {
                    "name": row["name"], "split": args.split, "plans": state["plans"],
                    "parsed": state["parsed"], "metrics": state["metrics"], "verification": state["verification"],
                    "complete": len(state["parsed"]) == len(base.ERROR_TYPES),
                }
                base.append_jsonl(partial_path, partial_record)
                if not partial_record["complete"]:
                    base.append_jsonl(
                        failed_path,
                        {
                            "name": row["name"], "split": args.split,
                            "retained_types": sorted(state["parsed"]),
                            "missing_types": [t for t in base.ERROR_TYPES if t not in state["parsed"]],
                            "feedback": state["feedback"],
                            "accepted_partial": bool(state["parsed"]),
                        },
                    )
                if state["parsed"]:
                    accepted_record = {
                        "name": row["name"], "split": args.split, "attempt": args.max_attempts,
                        "plans": state["plans"], "parsed": state["parsed"], "metrics": state["metrics"],
                        "verification": state["verification"],
                        "complete": partial_record["complete"], "accepted": True,
                    }
                    accepted[row["name"]] = accepted_record
                    base.append_jsonl(accepted_path, accepted_record)
                    print(
                        f"[accepted] name={row['name']} complete={partial_record['complete']} "
                        f"retained_types={sorted(state['parsed'])}", flush=True
                    )

            completed = min(batch_start + len(batch_rows), len(missing))
            elapsed = time.time() - started
            rate = completed / max(elapsed, 1e-6)
            eta_minutes = (len(missing) - completed) / max(rate, 1e-6) / 60
            print(
                f"[progress] split={args.split} samples={completed}/{len(missing)} "
                f"accepted_total={len(accepted)}/{len(rows)} elapsed_min={elapsed / 60:.1f} "
                f"eta_min={eta_minutes:.1f}",
                flush=True,
            )
            snapshot_every = max(1, args.batch_size) * 10
            if completed % snapshot_every == 0 or completed == len(missing):
                build_partial_outputs(
                    rows, accepted, output_dir, args.manual_review_samples, print_report=False
                )
                print(
                    f"[snapshot] samples={completed} quality={output_dir / 'quality_report.json'}",
                    flush=True,
                )

    report = build_partial_outputs(rows, accepted, output_dir, args.manual_review_samples)
    construction_counts: dict[str, dict[str, int]] = {
        wrong_type: {} for wrong_type in ERROR_TYPES
    }
    for record in accepted.values():
        for wrong_type in ERROR_TYPES:
            if wrong_type not in record.get("parsed", {}):
                continue
            source = str(record.get("plans", {}).get(wrong_type, {}).get("construction", "qwen3_generated"))
            construction_counts[wrong_type][source] = construction_counts[wrong_type].get(source, 0) + 1
    construction_report = {
        "accepted_by_type_and_construction": construction_counts,
    }
    (output_dir / "construction_report.json").write_text(
        json.dumps(construction_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest = {
        "generator_version": "controlled_error_qwen3_generate_verify_v1",
        "generator_family": args.generator_family,
        "generator_model": args.model,
        "split": args.split,
        "input_csv": args.input_csv,
        "selected_binary_samples": len(rows),
        "samples_with_any_verified_generated_type": report["samples_with_any_verified_generated_type"],
        "samples_with_all_four_verified_generated_types": report["samples_with_all_four_verified_generated_types"],
        "generated_type_pairs": report["generated_type_pairs"],
        "verification_stage": "external_qwen3_text",
        "max_length_delta_words": args.max_length_delta,
        "max_source_words": args.max_source_words,
        "min_lexical_jaccard": args.min_lexical_jaccard,
        "max_sentence_delta": args.max_sentence_delta,
        "max_attempts": args.max_attempts,
        "request_batch_size": args.batch_size,
        "generation_batch_size": args.generation_batch_size,
        "generation_messages_this_run": generated_calls,
        "elapsed_minutes": (time.time() - started) / 60,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
