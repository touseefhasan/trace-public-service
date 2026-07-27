from __future__ import annotations

import unittest
from pathlib import Path

from trace_engine.constraints import ConstraintParser
from trace_engine.ingestion import load_directory
from trace_engine.knowledge_graph import KnowledgeGraphQuery, build_knowledge_graph
from trace_engine.retrieval import VARIANT_FIELDS


SAMPLE_DATA = Path(__file__).parents[1] / "data" / "sample" / "pantries.csv"


class KnowledgeGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.providers = load_directory(SAMPLE_DATA)
        cls.parser = ConstraintParser(cls.providers)

    def test_kg1_materializes_location_nodes_and_edges(self) -> None:
        graph = build_knowledge_graph(self.providers, "kg1")
        summary = graph.summary()
        self.assertEqual(summary["node_kinds"]["ServiceProvider"], 5)
        self.assertEqual(summary["node_kinds"]["ServiceCategory"], 1)
        self.assertEqual(summary["relations"]["LOCATED_IN_CITY"], 5)
        self.assertEqual(summary["relations"]["LOCATED_IN_COUNTY"], 5)
        self.assertEqual(summary["relations"]["LOCATED_IN_ZIPCODE"], 5)
        self.assertEqual(summary["relations"]["IN_CATEGORY"], 5)
        self.assertNotIn("Hours", summary["node_kinds"])

    def test_kg2_traverses_hours_intervals(self) -> None:
        graph = build_knowledge_graph(self.providers, "kg2")
        constraints = self.parser.parse("Open Monday at 10am")
        identifiers = KnowledgeGraphQuery(graph).candidate_provider_ids(
            constraints,
            VARIANT_FIELDS["kg2"],
        )
        self.assertEqual(identifiers, frozenset({"ks-001", "ks-004"}))

    def test_kg3_intersects_location_and_hours_traversals(self) -> None:
        graph = build_knowledge_graph(self.providers, "kg3")
        constraints = self.parser.parse("In Sedgwick County open Monday at 5:30pm")
        identifiers = KnowledgeGraphQuery(graph).candidate_provider_ids(
            constraints,
            VARIANT_FIELDS["kg3"],
        )
        self.assertEqual(identifiers, frozenset({"ks-002"}))

    def test_graph_export_contains_typed_nodes_and_edges(self) -> None:
        payload = build_knowledge_graph(self.providers, "kg3").as_dict()
        self.assertTrue(any(node["kind"] == "County" for node in payload["nodes"]))
        self.assertTrue(
            any(edge["relation"] == "HAS_HOURS" for edge in payload["edges"])
        )


if __name__ == "__main__":
    unittest.main()
