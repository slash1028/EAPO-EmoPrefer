"""Export verified internal records into the public EAPO-EmoPrefer schema."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from . import dataset_utils as utils


CSV_FIELDS = [
    "sample_id", "split", "error_type", "preferred_description", "controlled_negative",
    "sentence_id", "source_phrase", "replacement_phrase", "target_modality", "construction",
    "preferred_words", "negative_words", "length_delta", "sentence_delta",
    "lexical_jaccard", "sequence_similarity", "observed_type", "targeted_error_present",
    "non_target_preserved", "fluent", "quality_score", "verified",
]

def read_latest_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("name"):
                records[str(item["name"])] = item
    return records


def public_record(
    sample_id: str,
    split: str,
    preferred: str,
    record: dict[str, Any],
    error_type: str,
) -> dict[str, Any]:
    plan = dict(record["plans"][error_type])
    candidate = dict(record["parsed"][error_type])
    metrics = dict(record.get("metrics", {}).get(error_type, {}))
    verification = dict(record.get("verification", {}).get(error_type, {}))
    observed_type = verification.get("predicted_type", verification.get("observed_type", ""))
    return {
        "sample_id": sample_id,
        "split": split,
        "error_type": error_type,
        "preferred_description": preferred,
        "controlled_negative": candidate.get("text", ""),
        "edit_plan": {
            "sentence_id": plan.get("sentence_id"),
            "source_phrase": plan.get("source_phrase", ""),
            "replacement_phrase": plan.get("replacement_phrase", ""),
            "target_modality": plan.get("target_modality", ""),
            "rationale": plan.get("rationale", ""),
            "construction": "qwen3_generated",
        },
        "automatic_metrics": {
            "preferred_words": metrics.get("preferred_words"),
            "negative_words": metrics.get("negative_words"),
            "length_delta": metrics.get("length_delta"),
            "sentence_delta": metrics.get("sentence_delta"),
            "lexical_jaccard": metrics.get("lexical_jaccard"),
            "sequence_similarity": metrics.get("sequence_similarity"),
        },
        "verification": {
            "observed_type": observed_type,
            "targeted_error_present": verification.get("targeted_error_present"),
            "non_target_preserved": verification.get("non_target_preserved"),
            "fluent": verification.get("fluent"),
            "quality_score": verification.get("quality_score"),
            "verified": bool(verification.get("pass")),
            "notes": verification.get("notes", ""),
        },
    }


def flatten(record: dict[str, Any]) -> dict[str, Any]:
    plan = record["edit_plan"]
    metrics = record["automatic_metrics"]
    verification = record["verification"]
    return {
        "sample_id": record["sample_id"],
        "split": record["split"],
        "error_type": record["error_type"],
        "preferred_description": record["preferred_description"],
        "controlled_negative": record["controlled_negative"],
        "sentence_id": plan["sentence_id"],
        "source_phrase": plan["source_phrase"],
        "replacement_phrase": plan["replacement_phrase"],
        "target_modality": plan["target_modality"],
        "construction": plan["construction"],
        **metrics,
        "observed_type": verification["observed_type"],
        "targeted_error_present": verification["targeted_error_present"],
        "non_target_preserved": verification["non_target_preserved"],
        "fluent": verification["fluent"],
        "quality_score": verification["quality_score"],
        "verified": verification["verified"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source_csv", required=True, help="CSV with name, a1, a2, preference columns.")
    parser.add_argument("--verified_jsonl", required=True)
    parser.add_argument("--split", required=True, choices=["train", "validation"])
    parser.add_argument("--output_dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = {
        row["name"]: row
        for row in utils.read_rows(Path(args.source_csv))
        if row.get("name") and utils.normalize_label(row.get("preference", "")) in {"a1", "a2"}
    }
    verified = read_latest_jsonl(Path(args.verified_jsonl))
    records: list[dict[str, Any]] = []
    records_by_sample: dict[str, list[dict[str, Any]]] = {}
    for sample_id in sorted(verified):
        source = source_rows.get(sample_id)
        if source is None:
            raise KeyError(f"verified sample missing from source CSV: {sample_id}")
        preferred, _ = utils.chosen_rejected(source)
        record = verified[sample_id]
        for error_type in utils.ERROR_TYPES:
            if error_type not in record.get("parsed", {}):
                continue
            item = public_record(sample_id, args.split, preferred, record, error_type)
            if not item["verification"]["verified"]:
                raise ValueError(f"unverified record reached public export: {sample_id}/{error_type}")
            records.append(item)
            records_by_sample.setdefault(sample_id, []).append(item)

    jsonl_path = output_dir / "controlled_negatives.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    with (output_dir / "controlled_negatives.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(flatten(record) for record in records)

    pair_rows: list[dict[str, Any]] = []
    for sample_id in sorted(source_rows):
        source = source_rows[sample_id]
        preferred, rejected = utils.chosen_rejected(source)
        original_metrics = {
            "preferred_words": utils.word_count(preferred),
            "negative_words": utils.word_count(rejected),
            "length_delta": utils.word_count(rejected) - utils.word_count(preferred),
            "lexical_jaccard": utils.lexical_jaccard(preferred, rejected),
            "sequence_similarity": utils.sequence_similarity(preferred, rejected),
        }
        pair_rows.append(
            utils.make_pair(sample_id, preferred, rejected, "original_rejected", original_metrics, False)
        )
        for record in records_by_sample.get(sample_id, []):
            pair_rows.append(
                utils.make_pair(
                    sample_id,
                    preferred,
                    record["controlled_negative"],
                    record["error_type"],
                    record["automatic_metrics"],
                    False,
                )
            )
    utils.write_rows(output_dir / "preference_pairs.csv", pair_rows, utils.PAIR_FIELDS)
    position_balanced = list(pair_rows)
    for row in pair_rows:
        preferred = row[row["preference"]]
        negative = row["a2"] if row["preference"] == "a1" else row["a1"]
        metrics = {
            "preferred_words": row["target_words"],
            "negative_words": row["negative_words"],
            "length_delta": row["length_delta"],
            "lexical_jaccard": row["lexical_jaccard"],
            "sequence_similarity": row["sequence_similarity"],
        }
        position_balanced.append(
            utils.make_pair(row["name"], preferred, negative, row["wrong_type"], metrics, True)
        )
    utils.write_rows(
        output_dir / "preference_pairs_position_balanced.csv",
        position_balanced,
        utils.PAIR_FIELDS,
    )

    type_counts = Counter(record["error_type"] for record in records)
    sample_counts = Counter(record["sample_id"] for record in records)
    statistics = {
        "split": args.split,
        "source_samples": len(source_rows),
        "samples_with_controlled_negatives": len(sample_counts),
        "samples_with_all_four_types": sum(count == len(utils.ERROR_TYPES) for count in sample_counts.values()),
        "controlled_negatives": len(records),
        "five_type_preference_pairs": len(pair_rows),
        "position_balanced_pair_rows": len(position_balanced),
        "counts_by_error_type": dict(sorted(type_counts.items())),
        "generator": "Qwen3-30B-A3B-Instruct-2507",
        "verifier": "Qwen3-30B-A3B-Instruct-2507",
        "construction": "qwen3_generated_and_qwen3_verified",
        "contains_media": False,
        "contains_raw_model_responses": False,
        "canonical_annotations_contain_candidate_order_augmentation": False,
    }
    (output_dir / "statistics.json").write_text(
        json.dumps(statistics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(statistics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
