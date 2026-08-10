from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from trace_engine.category_evaluation import load_category_benchmark
from trace_engine.ingestion import load_directory
from trace_engine.intent import OllamaCategoryClassifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Checkpoint Qwen benchmark classifications")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--ollama-model", default="qwen3.5:4b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--ollama-timeout", type=float, default=300.0)
    parser.add_argument("--allow-unvalidated", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cache_path = Path(args.cache)
    existing = []
    if cache_path.exists():
        existing = json.loads(cache_path.read_text(encoding="utf-8"))
    cached_queries = {item["query"] for item in existing}
    providers = load_directory(args.data)
    categories = tuple(sorted({item.category for item in providers if item.category}))
    cases = load_category_benchmark(
        args.benchmark, allow_unvalidated=args.allow_unvalidated
    )
    pending = [case.query for case in cases if case.query not in cached_queries]

    def classify(query: str) -> dict[str, object]:
        classifier = OllamaCategoryClassifier(
            model=args.ollama_model,
            base_url=args.ollama_url,
            timeout=args.ollama_timeout,
        )
        result = classifier.classify(query, categories)
        return {
            "query": query,
            "available_categories": list(categories),
            "categories": list(result.categories),
            "source": result.source,
            "evidence": list(result.evidence),
        }

    print(f"Starting with {len(existing)} cached; {len(pending)} pending", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(classify, query): query for query in pending}
        for future in as_completed(futures):
            item = future.result()
            existing.append(item)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Cached {len(existing)}/{len(cases)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
