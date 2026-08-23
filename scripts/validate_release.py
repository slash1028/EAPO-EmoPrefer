#!/usr/bin/env python3
"""Validate public data counts, verification gates, split integrity, and release hygiene."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_KEYS = {"raw_response", "raw_responses", "verification_response", "call_seconds"}
MEDIA_SUFFIXES = {".wav", ".mp3", ".mp4", ".avi", ".mov"}
ABSOLUTE_PATH = re.compile(r"(?:/n/work\d*/|/home/|[A-Za-z]:\\)")


def nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in nested_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in nested_keys(item)}
    return set()


def csv_count(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def main() -> None:
    split_ids: dict[str, set[str]] = {}
    total = 0
    for split in ("train", "validation"):
        split_dir = ROOT / "data" / split
        stats = json.loads((split_dir / "statistics.json").read_text(encoding="utf-8"))
        records = [
            json.loads(line)
            for line in (split_dir / "controlled_negatives.jsonl").open(encoding="utf-8")
            if line.strip()
        ]
        assert len(records) == stats["controlled_negatives"]
        assert csv_count(split_dir / "controlled_negatives.csv") == len(records)
        assert csv_count(split_dir / "preference_pairs.csv") == stats["five_type_preference_pairs"]
        assert (
            csv_count(split_dir / "preference_pairs_position_balanced.csv")
            == stats["position_balanced_pair_rows"]
        )
        keys = [(item["sample_id"], item["error_type"]) for item in records]
        assert len(keys) == len(set(keys)), f"duplicate controlled record in {split}"
        split_ids[split] = {item["sample_id"] for item in records}
        for item in records:
            verification = item["verification"]
            assert item["split"] == split
            assert item["edit_plan"]["construction"] == "qwen3_generated"
            assert verification["verified"] is True
            assert verification["observed_type"] == item["error_type"]
            assert verification["targeted_error_present"] is True
            assert verification["non_target_preserved"] is True
            assert verification["fluent"] is True
            assert 3 <= int(verification["quality_score"]) <= 5
            assert not (nested_keys(item) & FORBIDDEN_KEYS)
            assert not ABSOLUTE_PATH.search(json.dumps(item, ensure_ascii=False))
        total += len(records)

    assert not (split_ids["train"] & split_ids["validation"]), "sample ID leakage across splits"
    for path in ROOT.rglob("*"):
        if path.is_file():
            assert path.suffix.lower() not in MEDIA_SUFFIXES, f"media file included: {path}"
            assert path.stat().st_size < 100 * 1024 * 1024, f"file exceeds GitHub limit: {path}"
    print(f"Release validation passed: {total} controlled negatives; no split leakage or media files.")


if __name__ == "__main__":
    main()
