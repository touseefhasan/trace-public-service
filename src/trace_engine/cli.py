from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .engine import TraceEngine
from .evaluation import evaluate, load_benchmark
from .ingestion import load_directory
from .retrieval import VARIANT_FIELDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRACE public-service retrieval engine")
    parser.add_argument("--data", required=True, help="Path to a CSV or JSON provider directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="Retrieve grounded recommendations")
    ask.add_argument("query")
    ask.add_argument("--variant", choices=sorted(VARIANT_FIELDS), default="kg3")
    ask.add_argument("--limit", type=int, default=3)
    ask.add_argument("--batch-size", type=int, default=3)

    benchmark = subparsers.add_parser("evaluate", help="Evaluate a JSONL query benchmark")
    benchmark.add_argument("--benchmark", required=True)
    benchmark.add_argument("--variant", choices=sorted(VARIANT_FIELDS), default="kg3")
    benchmark.add_argument("--k", type=int, default=3)

    graph = subparsers.add_parser("graph", help="Inspect or export a materialized KG")
    graph.add_argument("--variant", choices=("kg1", "kg2", "kg3"), default="kg3")
    graph.add_argument("--output", help="Optional path for the full graph JSON export")

    subparsers.add_parser("list", help="Print the normalized provider directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    providers = load_directory(args.data)
    if args.command == "list":
        payload = [provider.as_dict() for provider in providers]
    elif args.command == "evaluate":
        engine = TraceEngine(providers, variant=args.variant)
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
        engine = TraceEngine(providers, variant=args.variant)
        payload = engine.recommend(
            args.query,
            limit=args.limit,
            batch_size=args.batch_size,
        ).as_dict()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
