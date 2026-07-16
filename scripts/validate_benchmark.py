from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from trace_engine.ingestion import load_directory
from trace_engine.models import Pantry
from trace_engine.normalization import normalize_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and repair source-derived TRACE benchmark ground truth"
    )
    parser.add_argument("--data", required=True, help="Kansas Food Source pantry CSV")
    parser.add_argument("--source", required=True, help="Source-derived benchmark JSONL")
    parser.add_argument("--output", required=True, help="Validated benchmark JSONL")
    return parser


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _recall_provider(query: str, providers: Sequence[Pantry]) -> Pantry:
    normalized_query = f" {normalize_text(query)} "
    matches = [
        provider
        for provider in providers
        if f" {normalize_text(provider.name)} " in normalized_query
    ]
    if not matches:
        raise ValueError(f"recall query does not contain a directory pantry name: {query}")
    longest = max(len(normalize_text(provider.name)) for provider in matches)
    best = [provider for provider in matches if len(normalize_text(provider.name)) == longest]
    if len(best) != 1:
        raise ValueError(f"recall query maps ambiguously to pantry names: {query}")
    return best[0]


def validate(data_path: Path, source_path: Path, output_path: Path) -> dict[str, int]:
    providers = load_directory(data_path)
    rows = _read_jsonl(source_path)
    repaired_recall = 0
    clarification_cases = 0

    for row in rows:
        family = row.get("family")
        if family == "recall":
            provider = _recall_provider(str(row["query"]), providers)
            row["source_gold_provider_names"] = row["gold_provider_names"]
            row["source_gold_provider_ids"] = row["gold_provider_ids"]
            row["source_num_matches_structural"] = row["num_matches_structural"]
            row["gold_provider_names"] = [provider.name]
            row["gold_provider_ids"] = [provider.provider_id]
            row["num_matches_structural"] = 1
            row["validation_note"] = "Recall ground truth repaired from pantry name in query."
            repaired_recall += 1
        elif family == "near_me":
            row["source_gold_provider_names"] = row["gold_provider_names"]
            row["source_gold_provider_ids"] = row["gold_provider_ids"]
            row["source_num_matches_structural"] = row["num_matches_structural"]
            row["gold_provider_names"] = []
            row["gold_provider_ids"] = []
            row["num_matches_structural"] = 0
            row["retrieval_evaluation_included"] = False
            row["expected_clarification"] = True
            row["validation_note"] = "No user location is available; clarification is expected."
            clarification_cases += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {
        "rows": len(rows),
        "repaired_recall": repaired_recall,
        "clarification_cases": clarification_cases,
    }


def main() -> int:
    args = build_parser().parse_args()
    summary = validate(Path(args.data), Path(args.source), Path(args.output))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
