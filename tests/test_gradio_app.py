from __future__ import annotations

import unittest

from trace_engine.engine import TraceEngine
from trace_engine.gradio_app import create_chat_handler, contextualize_query
from trace_engine.models import ServiceProvider


class GradioAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = TraceEngine(
            (
                ServiceProvider(
                    provider_id="shelter-1",
                    name="Wichita Shelter",
                    city="Wichita",
                    county="Sedgwick",
                    category="Housing & Shelter",
                    phone="316-555-0100",
                ),
            )
        )

    def test_chat_handler_returns_grounded_provider_answer(self) -> None:
        answer = create_chat_handler(self.engine)(
            "Where can I find shelter in Wichita?", []
        )
        self.assertIn("Wichita Shelter", answer)
        self.assertIn("316-555-0100", answer)

    def test_chat_handler_returns_clarification(self) -> None:
        answer = create_chat_handler(self.engine)("I need shelter", [])
        self.assertIn("Where are you looking", answer)

    def test_location_reply_is_attached_to_previous_request(self) -> None:
        history = [
            {"role": "user", "content": "I need shelter"},
            {
                "role": "assistant",
                "content": "Where are you looking for Housing & Shelter services?",
            },
        ]
        query = contextualize_query("Wichita", history)
        self.assertIn("I need shelter", query)
        self.assertIn("Wichita", query)


if __name__ == "__main__":
    unittest.main()
