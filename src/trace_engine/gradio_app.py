from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Sequence

from .engine import TraceEngine
from .generation import OllamaResponseGenerator, deterministic_chat_answer
from .ingestion import load_directory
from .intent import OllamaCategoryClassifier
from .retrieval import VARIANT_FIELDS


def contextualize_query(message: str, history: list[dict] | None) -> str:
    """Attach a short clarification reply to the preceding user request."""
    if not history or len(message.split()) > 8:
        return message

    last_assistant = next(
        (
            str(item.get("content", ""))
            for item in reversed(history)
            if item.get("role") == "assistant"
        ),
        "",
    )
    asks_for_context = (
        "Where are you looking" in last_assistant
        or "Which day should I check" in last_assistant
    )
    if not asks_for_context:
        return message

    previous_user = next(
        (
            str(item.get("content", ""))
            for item in reversed(history)
            if item.get("role") == "user"
        ),
        "",
    )
    return (
        f"{previous_user}. Additional clarification: {message}"
        if previous_user
        else message
    )


def create_chat_handler(
    engine: TraceEngine,
    *,
    limit: int = 3,
) -> Callable[[str, list[dict] | None], str]:
    """Create the small function expected by ``gr.ChatInterface``."""

    def chat(message: str, history: list[dict] | None) -> str:
        query = contextualize_query(message.strip(), history)
        if not query:
            return "Please enter a question about the service you need."
        result = engine.recommend(query, limit=limit)
        if result.answer:
            return result.answer
        if result.clarification:
            return result.clarification
        return deterministic_chat_answer(result.recommendations).text

    return chat


def create_engine(
    data_path: str,
    *,
    variant: str = "kg3",
    intent_classifier: str = "ollama",
    response_generator: str = "ollama",
    ollama_model: str = "qwen3.5:4b",
    ollama_url: str = "http://127.0.0.1:11434",
    ollama_timeout: float = 120,
    response_timeout: float = 240,
) -> TraceEngine:
    providers = load_directory(data_path)
    classifier = (
        OllamaCategoryClassifier(
            model=ollama_model,
            base_url=ollama_url,
            timeout=ollama_timeout,
        )
        if intent_classifier == "ollama"
        else None
    )
    generator = (
        OllamaResponseGenerator(
            model=ollama_model,
            base_url=ollama_url,
            timeout=response_timeout,
        )
        if response_generator == "ollama"
        else None
    )
    return TraceEngine(
        providers,
        variant=variant,
        category_classifier=classifier,
        response_generator=generator,
    )


def build_demo(engine: TraceEngine, *, limit: int = 3):
    try:
        import gradio as gr
    except ImportError as exc:
        raise RuntimeError(
            'Gradio is not installed. Run: python -m pip install -e ".[ui]"'
        ) from exc

    demo = gr.ChatInterface(
        fn=create_chat_handler(engine, limit=limit),
        title="TRACE Public-Service Assistant",
        description=(
            "Ask for public services by need and location. Recommendations are "
            "retrieved from the configured directory and retain source evidence."
        ),
        examples=[
            "Where can I find shelter in Wichita?",
            "I need chemotherapy treatment and a ride to the clinic in Wichita",
            "Which food services in Sedgwick County are open Saturday at 10am?",
        ],
        save_history=True,
    )
    return demo.queue(default_concurrency_limit=1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the TRACE Gradio chatbot")
    parser.add_argument("--data", required=True, help="CSV, JSON, or XLSX directory")
    parser.add_argument("--variant", choices=sorted(VARIANT_FIELDS), default="kg3")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument(
        "--intent-classifier",
        choices=("deterministic", "ollama"),
        default="ollama",
    )
    parser.add_argument(
        "--response-generator", choices=("deterministic", "ollama"), default="ollama"
    )
    parser.add_argument(
        "--ollama-model", default=os.environ.get("TRACE_OLLAMA_MODEL", "qwen3.5:4b")
    )
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("TRACE_OLLAMA_URL", "http://127.0.0.1:11434"),
    )
    parser.add_argument("--ollama-timeout", type=float, default=120)
    parser.add_argument("--response-timeout", type=float, default=240)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument(
        "--share", action="store_true", help="Create a temporary public Gradio URL"
    )
    parser.add_argument("--inbrowser", action="store_true")
    parser.add_argument("--username", help="Optional username for the Gradio page")
    parser.add_argument("--password", help="Optional password for the Gradio page")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if bool(args.username) != bool(args.password):
        raise SystemExit("--username and --password must be supplied together")
    engine = create_engine(
        args.data,
        variant=args.variant,
        intent_classifier=args.intent_classifier,
        response_generator=args.response_generator,
        ollama_model=args.ollama_model,
        ollama_url=args.ollama_url,
        ollama_timeout=args.ollama_timeout,
        response_timeout=args.response_timeout,
    )
    auth = (args.username, args.password) if args.username else None
    build_demo(engine, limit=args.limit).launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        inbrowser=args.inbrowser,
        auth=auth,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
