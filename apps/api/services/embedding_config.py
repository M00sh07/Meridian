"""Embedding configuration.

Model name and dimension are environment-configurable so the provider can be
swapped without a code change.
"""
import os

DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DEFAULT_DIMENSION = 384


def get_model_name() -> str:
    return os.getenv("EMBEDDING_MODEL_NAME", DEFAULT_MODEL_NAME)


def get_dimension() -> int:
    raw = os.getenv("EMBEDDING_DIMENSION", str(DEFAULT_DIMENSION))
    try:
        dimension = int(raw)
    except ValueError:
        return DEFAULT_DIMENSION
    if dimension <= 0:
        return DEFAULT_DIMENSION
    return dimension
