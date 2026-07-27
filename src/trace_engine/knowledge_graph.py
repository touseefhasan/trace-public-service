from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from .models import QueryConstraints, ServiceProvider
from .normalization import normalize_location, normalize_text, parse_clock, parse_hours


Scalar = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    kind: str
    properties: Mapping[str, Scalar] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    relation: str
    target: str
    properties: Mapping[str, Scalar] = field(default_factory=dict)


class PropertyGraph:
    """A small deterministic property graph with indexed nodes and typed edges."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self._outgoing: dict[str, dict[str, list[GraphEdge]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._incoming: dict[str, dict[str, list[GraphEdge]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._property_index: dict[tuple[str, str, Scalar], set[str]] = defaultdict(set)

    def add_node(self, node: GraphNode) -> None:
        existing = self.nodes.get(node.node_id)
        if existing and existing != node:
            raise ValueError(f"node ID already exists with different data: {node.node_id}")
        if existing:
            return
        self.nodes[node.node_id] = node
        for key, value in node.properties.items():
            self._property_index[(node.kind, key, value)].add(node.node_id)

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError(f"edge endpoints must exist: {edge.source} -> {edge.target}")
        self.edges.append(edge)
        self._outgoing[edge.source][edge.relation].append(edge)
        self._incoming[edge.target][edge.relation].append(edge)

    def find_nodes(self, kind: str, property_name: str, value: Scalar) -> tuple[GraphNode, ...]:
        identifiers = sorted(self._property_index.get((kind, property_name, value), set()))
        return tuple(self.nodes[node_id] for node_id in identifiers)

    def incoming(self, node_id: str, relation: str) -> tuple[GraphEdge, ...]:
        return tuple(self._incoming.get(node_id, {}).get(relation, ()))

    def outgoing(self, node_id: str, relation: str) -> tuple[GraphEdge, ...]:
        return tuple(self._outgoing.get(node_id, {}).get(relation, ()))

    def nodes_of_kind(self, kind: str) -> tuple[GraphNode, ...]:
        return tuple(node for node in self.nodes.values() if node.kind == kind)

    def summary(self) -> dict[str, Any]:
        node_kinds = Counter(node.kind for node in self.nodes.values())
        relations = Counter(edge.relation for edge in self.edges)
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "node_kinds": dict(sorted(node_kinds.items())),
            "relations": dict(sorted(relations.items())),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "nodes": [asdict(node) for node in self.nodes.values()],
            "edges": [asdict(edge) for edge in self.edges],
        }


def _node_id(kind: str, value: str) -> str:
    return f"{kind.casefold()}:{normalize_text(value)}"


def build_knowledge_graph(
    providers: Sequence[ServiceProvider], variant: str
) -> PropertyGraph:
    if variant not in {"kg1", "kg2", "kg3"}:
        raise ValueError("knowledge graphs are available for kg1, kg2, and kg3")

    include_location = variant in {"kg1", "kg3"}
    include_category = variant in {"kg1", "kg3"}
    include_hours = variant in {"kg2", "kg3"}
    graph = PropertyGraph()

    for provider in providers:
        provider_id = f"provider:{provider.provider_id}"
        graph.add_node(
            GraphNode(
                provider_id,
                "ServiceProvider",
                {
                    "provider_id": provider.provider_id,
                    "name": provider.name,
                    "normalized_name": normalize_text(provider.name),
                },
            )
        )

        if include_location:
            location_nodes = (
                (
                    GraphNode(
                        _node_id("city", provider.city),
                        "City",
                        {
                            "name": provider.city,
                            "normalized_name": normalize_location(provider.city),
                        },
                    ),
                    "LOCATED_IN_CITY",
                    provider.city,
                ),
                (
                    GraphNode(
                        _node_id("county", provider.county),
                        "County",
                        {
                            "name": provider.county,
                            "normalized_name": normalize_location(provider.county),
                        },
                    ),
                    "LOCATED_IN_COUNTY",
                    provider.county,
                ),
                (
                    GraphNode(
                        _node_id("zipcode", provider.zipcode),
                        "ZipCode",
                        {"value": provider.zipcode},
                    ),
                    "LOCATED_IN_ZIPCODE",
                    provider.zipcode,
                ),
            )
            for node, relation, value in location_nodes:
                if not value:
                    continue
                graph.add_node(node)
                graph.add_edge(GraphEdge(provider_id, relation, node.node_id))

        if include_category and provider.category:
            category_node = GraphNode(
                _node_id("category", provider.category),
                "ServiceCategory",
                {
                    "name": provider.category,
                    "normalized_name": normalize_text(provider.category),
                },
            )
            graph.add_node(category_node)
            graph.add_edge(GraphEdge(provider_id, "IN_CATEGORY", category_node.node_id))

        if include_hours:
            hours_id = f"hours:{provider.provider_id}"
            graph.add_node(GraphNode(hours_id, "Hours", {"raw_text": provider.hours}))
            graph.add_edge(GraphEdge(provider_id, "HAS_HOURS", hours_id))
            for day, intervals in parse_hours(provider.hours).items():
                day_node = GraphNode(_node_id("day", day), "Day", {"name": day})
                graph.add_node(day_node)
                for start, end in intervals:
                    graph.add_edge(
                        GraphEdge(
                            hours_id,
                            "OPEN_ON",
                            day_node.node_id,
                            {"start_minute": start, "end_minute": end},
                        )
                    )
    return graph


class KnowledgeGraphQuery:
    """Traverse graph relations and intersect the resulting provider node sets."""

    def __init__(self, graph: PropertyGraph) -> None:
        self.graph = graph

    @staticmethod
    def _provider_ids(nodes: Iterable[GraphNode]) -> set[str]:
        return {str(node.properties["provider_id"]) for node in nodes}

    def _providers_incoming_to(
        self, nodes: Iterable[GraphNode], relation: str
    ) -> set[str]:
        provider_node_ids = {
            edge.source for node in nodes for edge in self.graph.incoming(node.node_id, relation)
        }
        return self._provider_ids(
            self.graph.nodes[node_id] for node_id in provider_node_ids
        )

    def _hours_candidates(self, day: str | None, open_at: str | None) -> set[str]:
        if not day:
            return set()
        day_nodes = self.graph.find_nodes("Day", "name", day.casefold())
        minute = parse_clock(open_at) if open_at else None
        hours_ids: set[str] = set()
        for day_node in day_nodes:
            for edge in self.graph.incoming(day_node.node_id, "OPEN_ON"):
                start_value = edge.properties["start_minute"]
                end_value = edge.properties["end_minute"]
                start = int(start_value) if start_value is not None else None
                end = int(end_value) if end_value is not None else None
                if minute is None or (
                    start is not None and end is not None and start <= minute < end
                ):
                    hours_ids.add(edge.source)
        provider_node_ids = {
            edge.source
            for hours_id in hours_ids
            for edge in self.graph.incoming(hours_id, "HAS_HOURS")
        }
        return self._provider_ids(
            self.graph.nodes[node_id] for node_id in provider_node_ids
        )

    def candidate_provider_ids(
        self,
        constraints: QueryConstraints,
        exact_fields: frozenset[str],
    ) -> frozenset[str]:
        filters: list[set[str]] = []
        if "provider_name" in exact_fields and constraints.provider_name:
            filters.append(
                self._provider_ids(
                    self.graph.find_nodes(
                        "ServiceProvider",
                        "normalized_name",
                        normalize_text(constraints.provider_name),
                    )
                )
            )
        if "city" in exact_fields and constraints.city:
            filters.append(
                self._providers_incoming_to(
                    self.graph.find_nodes(
                        "City", "normalized_name", normalize_location(constraints.city)
                    ),
                    "LOCATED_IN_CITY",
                )
            )
        if "county" in exact_fields and constraints.county:
            filters.append(
                self._providers_incoming_to(
                    self.graph.find_nodes(
                        "County", "normalized_name", normalize_location(constraints.county)
                    ),
                    "LOCATED_IN_COUNTY",
                )
            )
        if "zipcode" in exact_fields and constraints.zipcode:
            filters.append(
                self._providers_incoming_to(
                    self.graph.find_nodes("ZipCode", "value", constraints.zipcode),
                    "LOCATED_IN_ZIPCODE",
                )
            )
        if "category" in exact_fields and constraints.category:
            filters.append(
                self._providers_incoming_to(
                    self.graph.find_nodes(
                        "ServiceCategory",
                        "normalized_name",
                        normalize_text(constraints.category),
                    ),
                    "IN_CATEGORY",
                )
            )
        if {"day", "open_at"} & exact_fields and (constraints.day or constraints.open_at):
            filters.append(self._hours_candidates(constraints.day, constraints.open_at))

        if not filters:
            return frozenset(
                str(node.properties["provider_id"])
                for node in self.graph.nodes_of_kind("ServiceProvider")
            )
        candidates = set(filters[0])
        for values in filters[1:]:
            candidates &= values
        return frozenset(candidates)
