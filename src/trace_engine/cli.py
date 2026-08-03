from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from .engine import TraceEngine
from .evaluation import evaluate, load_benchmark
from .generation import OllamaResponseGenerator
from .ingestion import load_directory
from .intent import OllamaCategoryClassifier
from .retrieval import VARIANT_FIELDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRACE public-service retrieval engine")
    parser.add_argument(
        "--data",
        required=True,
        help="Path to a CSV, JSON, or XLSX service-provider directory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="Retrieve grounded recommendations")
    ask.add_argument("query")
    ask.add_argument("--variant", choices=sorted(VARIANT_FIELDS), default="kg3")
    ask.add_argument("--limit", type=int, default=3)
    ask.add_argument("--batch-size", type=int, default=3)
    _add_intent_classifier_arguments(ask)
    ask.add_argument(
        "--response-generator",
        choices=("none", "ollama"),
        default="none",
        help="Optional grounded chat response generator; default preserves retrieval-only JSON",
    )
    ask.add_argument(
        "--response-timeout",
        type=float,
        default=float(os.environ.get("TRACE_RESPONSE_TIMEOUT", "240")),
        help="Seconds allowed for the longer grounded response-generation call",
    )

    benchmark = subparsers.add_parser("evaluate", help="Evaluate a JSONL query benchmark")
    benchmark.add_argument("--benchmark", required=True)
    benchmark.add_argument("--variant", choices=sorted(VARIANT_FIELDS), default="kg3")
    benchmark.add_argument("--k", type=int, default=3)
    _add_intent_classifier_arguments(benchmark)

    graph = subparsers.add_parser("graph", help="Inspect or export a materialized KG")
    graph.add_argument("--variant", choices=("kg1", "kg2", "kg3"), default="kg3")
    graph.add_argument("--output", help="Optional path for the full graph JSON export")

    subparsers.add_parser("list", help="Print the normalized provider directory")
    return parser


def _add_intent_classifier_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--intent-classifier",
        choices=("deterministic", "ollama"),
        default="deterministic",
        help="Category classifier; Ollama runs locally and falls back deterministically",
    )
    parser.add_argument(
        "--ollama-model",
        default=os.environ.get("TRACE_OLLAMA_MODEL", "qwen3.5:4b"),
        help="Local Ollama model used for multi-label category classification",
    )
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("TRACE_OLLAMA_URL", "http://127.0.0.1:11434"),
        help="Ollama API base URL",
    )
    parser.add_argument(
        "--ollama-timeout",
        type=float,
        default=float(os.environ.get("TRACE_OLLAMA_TIMEOUT", "120")),
        help="Seconds allowed for local classification; default 120",
    )


def _category_classifier(args: argparse.Namespace) -> OllamaCategoryClassifier | None:
    if getattr(args, "intent_classifier", "deterministic") != "ollama":
        return None
    return OllamaCategoryClassifier(
        model=args.ollama_model,
        base_url=args.ollama_url,
        timeout=args.ollama_timeout,
    )


def _response_generator(args: argparse.Namespace) -> OllamaResponseGenerator | None:
    if getattr(args, "response_generator", "none") != "ollama":
        return None
    return OllamaResponseGenerator(
        model=args.ollama_model,
        base_url=args.ollama_url,
        timeout=args.response_timeout,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    providers = load_directory(args.data)
    if args.command == "list":
        payload = [provider.as_dict() for provider in providers]
    elif args.command == "evaluate":
        engine = TraceEngine(
            providers,
            variant=args.variant,
            category_classifier=_category_classifier(args),
        )
        payload = evaluate(engine, load_benchmark(args.benchmark), k=args.k).as_dict()
    elif args.command == "graph":
        engine = TraceEngine(providers, variant=args.variant)
        graph = engine.retriever.graph
        if graph is None:
            raise RuntimeError("selected variant does not materialize a graph")
        payload = graph.summary()
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(graph.as_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            payload["output"] = str(output)
    else:
        engine = TraceEngine(
            providers,
            variant=args.variant,
            category_classifier=_category_classifier(args),
            response_generator=_response_generator(args),
        )
        payload = engine.recommend(
            args.query,
            limit=args.limit,
            batch_size=args.batch_size,
        ).as_dict()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
