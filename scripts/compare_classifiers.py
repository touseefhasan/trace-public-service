from __future__ import annotations

import argparse
import json
from pathlib import Path

from trace_engine.category_evaluation import evaluate_categories, load_category_benchmark
from trace_engine.constraint_evaluation import (
    evaluate_constraint_retrieval,
    load_constraint_cases,
)
from trace_engine.ingestion import load_directory
from trace_engine.intent import (
    CategoryClassification,
    CategoryClassifier,
    DeterministicCategoryClassifier,
    OllamaCategoryClassifier,
)


class CachedClassifier:
    def __init__(self, classifier: CategoryClassifier, cache_path: Path | None = None) -> None:
        self.classifier = classifier
        self.cache: dict[tuple[str, tuple[str, ...]], CategoryClassification] = {}
        self.cache_path = cache_path
        if cache_path and cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            for item in payload:
                key = (item["query"], tuple(item["available_categories"]))
                self.cache[key] = CategoryClassification(
                    tuple(item["categories"]), item["source"], tuple(item["evidence"])
                )

    def _save(self) -> None:
        if not self.cache_path:
            return
        payload = [
            {
                "query": query,
                "available_categories": list(available),
                "categories": list(result.categories),
                "source": result.source,
                "evidence": list(result.evidence),
            }
            for (query, available), result in self.cache.items()
        ]
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def classify(
        self, query: str, available_categories: tuple[str, ...]
    ) -> CategoryClassification:
        # Taxonomy order differs between the standalone classifier evaluator and
        # ConstraintParser, but the set of allowable labels is identical.
        key = (query, tuple(sorted(set(available_categories))))
        if key not in self.cache:
            self.cache[key] = self.classifier.classify(query, available_categories)
            self._save()
        return self.cache[key]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare deterministic and Qwen classification plus KG retrieval"
    )
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--variant", choices=("kg0", "kg1", "kg2", "kg3"), default="kg3")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--ollama-model", default="qwen3.5:4b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--ollama-timeout", type=float, default=120.0)
    parser.add_argument("--allow-unvalidated", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    providers = load_directory(args.data)
    categories = tuple(sorted({provider.category for provider in providers if provider.category}))
    category_cases = load_category_benchmark(
        args.benchmark, allow_unvalidated=args.allow_unvalidated
    )
    constraint_cases = load_constraint_cases(
        args.benchmark, allow_unvalidated=args.allow_unvalidated
    )

    deterministic = DeterministicCategoryClassifier()
    deterministic_category = evaluate_categories(
        deterministic,
        category_cases,
        categories,
        classifier_name="deterministic",
    )
    deterministic_retrieval = evaluate_constraint_retrieval(
        providers,
        constraint_cases,
        variant=args.variant,
        limit=args.limit,
        classifier_name="deterministic",
    )

    output = Path(args.output)
    qwen = CachedClassifier(
        OllamaCategoryClassifier(
            model=args.ollama_model,
            base_url=args.ollama_url,
            timeout=args.ollama_timeout,
        ),
        output.with_suffix(".qwen-cache.json"),
    )
    qwen_category = evaluate_categories(
        qwen,
        category_cases,
        categories,
        classifier_name=args.ollama_model,
    )
    qwen_retrieval = evaluate_constraint_retrieval(
        providers,
        constraint_cases,
        variant=args.variant,
        limit=args.limit,
        category_classifier=qwen,
        classifier_name=args.ollama_model,
    )

    result = {
        "protocol": {
            "queries": len(category_cases),
            "variant": args.variant,
            "limit": args.limit,
            "labels_are_provisional": args.allow_unvalidated,
            "qwen_model": args.ollama_model,
        },
        "deterministic": {
            "category_metrics": deterministic_category.as_dict(),
            "retrieval": deterministic_retrieval,
        },
        "qwen": {
            "category_metrics": qwen_category.as_dict(),
            "retrieval": qwen_retrieval,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "deterministic_category": deterministic_category.as_dict(),
        "qwen_category": qwen_category.as_dict(),
        "deterministic_retrieval": deterministic_retrieval["metrics"],
        "qwen_retrieval": qwen_retrieval["metrics"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
