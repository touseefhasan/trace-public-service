from __future__ import annotations

import argparse
import json

from trace_engine.constraint_evaluation import (
    evaluate_constraint_retrieval,
    load_constraint_cases,
    write_constraint_evaluation,
)
from trace_engine.ingestion import load_directory
from trace_engine.intent import OllamaCategoryClassifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate returned providers against query constraints rather than provider IDs"
    )
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--variant", choices=("kg0", "kg1", "kg2", "kg3"), default="kg3")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--output", help="Optional detailed JSON output path")
    parser.add_argument("--allow-unvalidated", action="store_true")
    parser.add_argument(
        "--classifier", choices=("deterministic", "ollama"), default="deterministic"
    )
    parser.add_argument("--ollama-model", default="qwen3.5:4b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--ollama-timeout", type=float, default=120.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cases = load_constraint_cases(
        args.benchmark,
        allow_unvalidated=args.allow_unvalidated,
    )
    result = evaluate_constraint_retrieval(
        load_directory(args.data),
        cases,
        variant=args.variant,
        limit=args.limit,
        category_classifier=(
            OllamaCategoryClassifier(
                model=args.ollama_model,
                base_url=args.ollama_url,
                timeout=args.ollama_timeout,
            )
            if args.classifier == "ollama"
            else None
        ),
        classifier_name=(
            args.ollama_model if args.classifier == "ollama" else "deterministic"
        ),
    )
    if args.output:
        write_constraint_evaluation(result, args.output)
    print(json.dumps(result["metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
