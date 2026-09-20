"""Portable vector column type.

Uses pgvector's `Vector` on PostgreSQL and a JSON text representation on other
dialects, so SQLite (local dev and the Phase 4.1 tests) keeps working without a
running Postgres instance while PostgreSQL gets a real vector(n) column that
supports cosine distance.
"""
import json
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector as _PgVector
    PGVECTOR_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    _PgVector = None
    PGVECTOR_AVAILABLE = False


class _JsonVector(TypeDecorator):
    # JSON-serialized float list used on non-PostgreSQL dialects. Gives the
    # column a concrete SQL type (TEXT) there while values round-trip as floats.

    impl = Text
    cache_ok = True
    def __init__(self, dimension: int):
        super().__init__()
        self.dimension = dimension
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps([float(v) for v in value])

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [float(v) for v in value]
        return [float(v) for v in json.loads(value)]

class VectorAdapter(TypeDecorator):
    # pgvector-backed vector column, rendered as vector(dimension) on PostgreSQL
    # and TEXT (JSON) elsewhere. TypeDecorator routes bind/result processing
    # through this class on every dialect, which UserDefinedType does not.

    impl = Text
    cache_ok = True
    def __init__(self, dimension: int):
        super().__init__()
        self.dimension = dimension
    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            return dialect.type_descriptor(_PgVector(self.dimension))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            return list(value)
        return json.dumps([float(v) for v in value])

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [float(v) for v in value]
        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            return [float(v) for v in value]
        return [float(v) for v in json.loads(value)]


def build_vector_type(dimension: int):
    # Returns a dialect-adapting vector type: real vector(n) on PostgreSQL,
    # JSON text elsewhere.
    # PostgreSQL gets a real vector(n) column; other dialects store JSON text.
    if PGVECTOR_AVAILABLE:
        return VectorAdapter(dimension)
    return _JsonVector(dimension)









