from __future__ import annotations

import argparse
import json

from trace_engine.category_evaluation import evaluate_categories, load_category_benchmark
from trace_engine.ingestion import load_directory
from trace_engine.intent import DeterministicCategoryClassifier, OllamaCategoryClassifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate TRACE multi-label category extraction")
    parser.add_argument("--benchmark", required=True, help="Annotation workbook or JSONL benchmark")
    parser.add_argument("--data", required=True, help="211 provider directory used for its taxonomy")
    parser.add_argument(
        "--classifier", choices=("deterministic", "ollama"), default="deterministic"
    )
    parser.add_argument("--ollama-model", default="qwen3.5:4b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--ollama-timeout", type=float, default=120.0)
    parser.add_argument(
        "--allow-unvalidated",
        action="store_true",
        help="Development only: evaluate provisional Needs Review labels",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    providers = load_directory(args.data)
    categories = tuple(sorted({provider.category for provider in providers if provider.category}))
    classifier = (
        OllamaCategoryClassifier(
            model=args.ollama_model,
            base_url=args.ollama_url,
            timeout=args.ollama_timeout,
        )
        if args.classifier == "ollama"
        else DeterministicCategoryClassifier()
    )
    cases = load_category_benchmark(
        args.benchmark,
        allow_unvalidated=args.allow_unvalidated,
    )
    metrics = evaluate_categories(
        classifier,
        cases,
        categories,
        classifier_name=args.classifier if args.classifier == "deterministic" else args.ollama_model,
    )
    print(json.dumps(metrics.as_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
