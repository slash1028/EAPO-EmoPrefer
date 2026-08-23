"""Shared text, CSV, JSONL, and preference-pair utilities."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ERROR_TYPES = (
    "emotion_flip",
    "intensity_mismatch",
    "evidence_contradiction",
    "modality_omission",
)
ALL_TYPES = ("original_rejected",) + ERROR_TYPES
TYPE_ALIASES = {
    "emotion flip": "emotion_flip",
    "emotion_flip": "emotion_flip",
    "intensity mismatch": "intensity_mismatch",
    "intensity_mismatch": "intensity_mismatch",
    "evidence contradiction": "evidence_contradiction",
    "evidence_contradiction": "evidence_contradiction",
    "modality omission": "modality_omission",
    "modality_omission": "modality_omission",
    "modality underspecification": "modality_omission",
    "modality_underspecification": "modality_omission",
}
PAIR_FIELDS = [
    "pair_id", "name", "a1", "a2", "preference", "wrong_type", "source_name",
    "is_swapped", "positive_source", "source", "target_words", "negative_words",
    "length_delta", "lexical_jaccard", "sequence_similarity",
]
AUDIT_FIELDS = [
    "name", "wrong_type", "preferred", "negative", "official_rejected",
    "preferred_words", "negative_words", "length_delta", "sentence_delta",
    "lexical_jaccard", "sequence_similarity", "semantic_verifier_pass",
    "semantic_verifier_notes",
]


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\r", " ").replace("\t", " ")).strip()


def normalize_label(value: str) -> str:
    value = clean_text(value).lower()
    return value if value in {"a1", "a2"} else "same"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", clean_text(text).lower())


def word_count(text: str) -> int:
    return len(word_tokens(text))


def sentence_count(text: str) -> int:
    pieces = [part for part in re.split(r"[.!?]+", clean_text(text)) if part.strip()]
    return max(1, len(pieces))


def lexical_jaccard(left: str, right: str) -> float:
    left_set, right_set = set(word_tokens(left)), set(word_tokens(right))
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0


def sequence_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, clean_text(left).lower(), clean_text(right).lower()).ratio()


def chosen_rejected(row: dict[str, str]) -> tuple[str, str]:
    label = normalize_label(row.get("preference", ""))
    if label == "a1":
        return clean_text(row.get("a1", "")), clean_text(row.get("a2", ""))
    if label == "a2":
        return clean_text(row.get("a2", "")), clean_text(row.get("a1", ""))
    raise ValueError(f"sample {row.get('name', '')} is not binary")


def normalize_type(value: str) -> str:
    key = clean_text(value).lower().replace("-", "_")
    return TYPE_ALIASES.get(key, TYPE_ALIASES.get(key.replace("_", " "), key))


def model_messages(model: Any, row: dict[str, str], prompt: str, data_root: Path, input_type: str) -> Any:
    """Build model input while retaining compatibility with text-only and multimodal adapters."""
    name = row["name"]
    return model.generate_message(
        str(data_root / "audio" / f"{name}.wav"),
        str(data_root / "video" / f"{name}.mp4"),
        prompt,
        input_type,
    )


def load_accepted(path: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return output
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if record.get("accepted") and record.get("name") and isinstance(record.get("parsed"), dict):
                output[str(record["name"])] = record
    return output


def stable_preferred_first(name: str, wrong_type: str) -> bool:
    digest = hashlib.sha256(f"{name}:{wrong_type}".encode()).hexdigest()
    return int(digest[:8], 16) % 2 == 0


def make_pair(
    name: str,
    preferred: str,
    negative: str,
    wrong_type: str,
    metrics: dict[str, Any],
    swapped: bool,
) -> dict[str, Any]:
    preferred_first = stable_preferred_first(name, wrong_type)
    if swapped:
        preferred_first = not preferred_first
    a1, a2 = (preferred, negative) if preferred_first else (negative, preferred)
    return {
        "pair_id": f"{name}::{wrong_type}::{'swap' if swapped else 'base'}",
        "name": name,
        "a1": a1,
        "a2": a2,
        "preference": "a1" if preferred_first else "a2",
        "wrong_type": wrong_type,
        "source_name": name,
        "is_swapped": "1" if swapped else "0",
        "positive_source": "official_preferred",
        "source": "official" if wrong_type == "original_rejected" else "controlled_qwen3_text",
        "target_words": metrics.get("preferred_words", word_count(preferred)),
        "negative_words": metrics.get("negative_words", word_count(negative)),
        "length_delta": metrics.get("length_delta", word_count(negative) - word_count(preferred)),
        "lexical_jaccard": f"{float(metrics.get('lexical_jaccard', lexical_jaccard(preferred, negative))):.6f}",
        "sequence_similarity": f"{float(metrics.get('sequence_similarity', sequence_similarity(preferred, negative))):.6f}",
    }
