#!/usr/bin/env python3
"""Verify rule-valid error candidates with Qwen3 text-only."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from . import generate as v11


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def load_latest(path: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return output
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if item.get("name"):
                output[str(item["name"])] = item
    return output


class Qwen3TextVerifier:
    """Audit preferred/negative edit pairs without loading audio or video inputs."""

    def __init__(self, model_root: str):
        os.environ["QWEN3_TEXT_MAX_NEW_TOKENS"] = os.environ.get(
            "QWEN3_TEXT_VERIFY_MAX_NEW_TOKENS", "480"
        )
        print(f"[verifier] Qwen3 text-only model={model_root}", flush=True)
        self.generator = v11.Qwen3TextGenerator(model_root)

    def verify(self, prompt: str, name: str) -> str:
        return self.generator.func_calling([prompt], batch_size=1, names=[name])[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input_csv", required=True)
    parser.add_argument("--split", required=True, choices=["train", "val"])
    parser.add_argument("--candidate_dir", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--max_samples", type=int, default=0)
    parser.add_argument("--manual_review_samples", type=int, default=100)
    parser.add_argument("--snapshot_every", type=int, default=20)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidate_dir = Path(args.candidate_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    verification_path = output_dir / "qwen3text_verification_results.jsonl"
    accepted_path = output_dir / "accepted_generations.jsonl"
    if args.force:
        for path in (verification_path, accepted_path):
            if path.exists():
                path.unlink()

    rows = [
        row for row in v11.base.read_rows(Path(args.input_csv))
        if v11.base.normalize_label(row.get("preference", "")) in {"a1", "a2"}
    ]
    if args.max_samples > 0:
        rows = rows[: args.max_samples]
    source = v11.base.load_accepted(candidate_dir / "accepted_generations.jsonl")
    done = load_latest(verification_path)
    accepted = {
        name: record for name, record in done.items()
        if isinstance(record.get("parsed"), dict) and record["parsed"]
    }
    pending = [row for row in rows if row.get("name") in source and row["name"] not in done]
    print(
        f"[info] split={args.split} rows={len(rows)} generated={len(source)} "
        f"done={len(done)} pending={len(pending)}",
        flush=True,
    )
    if pending:
        model = Qwen3TextVerifier(args.model)
        started = time.time()
        for index, row in enumerate(pending, 1):
            name = row["name"]
            candidate_record = source[name]
            candidates = {
                key: value for key, value in candidate_record.get("parsed", {}).items()
                if key in v11.ERROR_TYPES
            }
            plans = {
                key: value for key, value in candidate_record.get("plans", {}).items()
                if key in candidates
            }
            response = ""
            try:
                prompt = v11.corrected_verifier_prompt(row, candidates, plans)
                response = model.verify(prompt, f"{name}:qwen3_text_verify")
                errors, assessments = v11.parse_corrected_verification(
                    response, list(candidates)
                )
            except Exception as exc:  # noqa: BLE001
                errors = [f"verification failure: {exc}"]
                assessments = {}
            passed_types = [
                wrong_type for wrong_type in candidates
                if assessments.get(wrong_type, {}).get("pass") is True
            ]
            record = {
                "name": name,
                "split": args.split,
                "plans": {key: plans[key] for key in passed_types},
                "parsed": {key: candidates[key] for key in passed_types},
                "metrics": {
                    key: candidate_record.get("metrics", {}).get(key, {}) for key in passed_types
                },
                "verification": assessments,
                "source_candidate_types": sorted(candidates),
                "passed_types": sorted(passed_types),
                "rejected_types": sorted(set(candidates) - set(passed_types)),
                "errors": errors,
                "raw_response": response,
                "accepted": bool(passed_types),
                "complete": len(passed_types) == len(v11.ERROR_TYPES),
            }
            done[name] = record
            append_jsonl(verification_path, record)
            if passed_types:
                accepted[name] = record
                append_jsonl(accepted_path, record)
            elapsed = time.time() - started
            rate = index / max(elapsed, 1e-6)
            eta = (len(pending) - index) / max(rate, 1e-6) / 60
            print(
                f"[verified] {index}/{len(pending)} name={name} passed={sorted(passed_types)} "
                f"rejected={record['rejected_types']} eta_min={eta:.1f}",
                flush=True,
            )
            if index % max(1, args.snapshot_every) == 0 or index == len(pending):
                v11.build_partial_outputs(
                    rows, accepted, output_dir, args.manual_review_samples, print_report=False
                )
                print(f"[snapshot] {output_dir / 'quality_report.json'}", flush=True)

    report = v11.build_partial_outputs(rows, accepted, output_dir, args.manual_review_samples)
    construction_counts: dict[str, dict[str, int]] = {wrong_type: {} for wrong_type in v11.ERROR_TYPES}
    for record in accepted.values():
        for wrong_type in v11.ERROR_TYPES:
            if wrong_type not in record.get("parsed", {}):
                continue
            source_name = str(record.get("plans", {}).get(wrong_type, {}).get("construction", "qwen3_generated"))
            construction_counts[wrong_type][source_name] = construction_counts[wrong_type].get(source_name, 0) + 1
    (output_dir / "construction_report.json").write_text(
        json.dumps({"accepted_by_type_and_construction": construction_counts}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "verifier": "qwen3_text_v1_negative_quality",
        "model": args.model,
        "uses_multimodal_input": False,
        "uses_preference_labels": False,
        "split": args.split,
        "rows": len(rows),
        "generated_samples": len(source),
        "verified_samples": len(done),
        "accepted_samples": len(accepted),
        "generated_type_pairs_after_verification": report["generated_type_pairs"],
    }
    (output_dir / "qwen3text_verifier_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
