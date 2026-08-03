"""TRACE public-service retrieval engine."""

from .engine import TraceEngine
from .generation import GeneratedAnswer, OllamaResponseGenerator, ResponseGenerator
from .intent import (
    CategoryClassification,
    CategoryClassifier,
    DeterministicCategoryClassifier,
    OllamaCategoryClassifier,
)
from .models import Pantry, QueryConstraints, ServiceProvider, TraceResult

__all__ = [
    "Pantry",
    "CategoryClassification",
    "CategoryClassifier",
    "DeterministicCategoryClassifier",
    "OllamaCategoryClassifier",
    "GeneratedAnswer",
    "OllamaResponseGenerator",
    "QueryConstraints",
    "ResponseGenerator",
    "ServiceProvider",
    "TraceEngine",
    "TraceResult",
]
