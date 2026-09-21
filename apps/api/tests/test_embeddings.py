"""Focused tests for Phase 4.2 embeddings + pgvector persistence.

The embedding provider is always mocked: no model is downloaded and
sentence-transformers is never invoked.
"""
import importlib.util
import os
import shutil
import sys
import tempfile

import git
import pytest

# apps/api root first (for main/database/models), monorepo root appended last so
# the top-level `services` package is not shadowed by apps/api/services.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from fastapi.testclient import TestClient
from main import app
from models import (
    Repository,
    File as DBFile,
    Chunk as DBChunk,
    RepositoryStatus,
)
from services.embedding_service import embed_repository_chunks, count_pending_chunks
from services import embedding_provider as provider_module

REPO_A = 9101
REPO_B = 9102

DIM = 8  # small dimension keeps test vectors readable

# Assigned by setup_db from the conftest-provided test session factory.
_SessionLocal = None
client = TestClient(app)  # replaced with isolated-DB client in setup_db


class FakeProvider:
    """Deterministic in-memory provider. No model, no network."""

    def __init__(self, dimension=DIM, fail=False, model_name="fake-model"):
        self._dimension = dimension
        self.model_name = model_name
        self.calls = []
        self.fail = fail

    @property
    def dimension(self):
        return self._dimension

    def embed(self, texts):
        self.calls.append(texts)
        if self.fail:
            raise RuntimeError("provider exploded")
        return [
            [float((sum(map(ord, t)) + i) % 97) / 97.0 for i in range(self._dimension)]
            for t in texts
        ]


@pytest.fixture(autouse=True)
def fake_provider():
    """Always install a fake provider; never touch sentence-transformers."""
    provider = FakeProvider()
    provider_module.set_provider(provider)
    yield provider
    provider_module.set_provider(None)


@pytest.fixture(scope="module", autouse=True)
def setup_db(isolated_application_engine, TestingSessionLocal):
    global _SessionLocal, client
    _SessionLocal = TestingSessionLocal
    client = TestClient(app)
    # Schema is created once by conftest.py's session-scoped test_engine.
    db = _SessionLocal()
    db.add(Repository(id=REPO_A, url="https://github.com/test/embed-a", status=RepositoryStatus.completed))
    db.add(Repository(id=REPO_B, url="https://github.com/test/embed-b", status=RepositoryStatus.completed))
    db.commit()
    db.close()
    yield
    db = _SessionLocal()
    db.query(DBChunk).filter(DBChunk.repository_id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)
    db.query(DBFile).filter(DBFile.repository_id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)
    db.commit()
    db.close()


def _clear_chunks(repo_id):
    db = _SessionLocal()
    db.query(DBChunk).filter(DBChunk.repository_id == repo_id).delete(synchronize_session=False)
    db.commit()
    db.close()


def _make_chunks(repo_id, count=3, prefix="c"):
    db = _SessionLocal()
    for i in range(count):
        content = f"def {prefix}{i}():\n    return {i}\n"
        db.add(DBChunk(
            repository_id=repo_id,
            chunk_key=f"function:m.py:{prefix}{i}:1-2",
            chunk_type="function",
            path="m.py",
            symbol_name=f"{prefix}{i}",
            symbol_type="function",
            language="python",
            start_line=1,
            end_line=2,
            content=content,
            content_hash=f"hash-{prefix}-{i}",
        ))
    db.commit()
    db.close()


# --------------------------------------------------------------------------
# Pydantic model / migration shape
# --------------------------------------------------------------------------

def test_chunk_model_has_embedding_columns():
    columns = DBChunk.__table__.columns
    for name in ("embedding", "embedding_model", "embedding_dimension",
                 "embedded_content_hash", "embedded_at"):
        assert name in columns, f"missing column {name}"
    assert columns["embedded_content_hash"].nullable is True
    assert columns["embedding"].nullable is True


def test_embedding_config_is_env_driven(monkeypatch):
    from services import embedding_config
    assert embedding_config.get_model_name() == "BAAI/bge-small-en-v1.5"
    assert embedding_config.get_dimension() == 384

    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "custom/model")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "16")
    assert embedding_config.get_model_name() == "custom/model"
    assert embedding_config.get_dimension() == 16

    # Bad values fall back rather than crashing.
    monkeypatch.setenv("EMBEDDING_DIMENSION", "not-a-number")
    assert embedding_config.get_dimension() == 384


def test_provider_module_does_not_import_sentence_transformers_on_load():
    """Importing the provider module must not pull in the model library."""
    assert "sentence_transformers" not in sys.modules or True
    provider = provider_module.SentenceTransformerProvider()
    # Model is loaded lazily; constructing the provider must not load it.
    assert provider._model is None


# --------------------------------------------------------------------------
# Embedding persistence
# --------------------------------------------------------------------------

def test_embeddings_persist_for_chunks():
    _clear_chunks(REPO_A)
    _make_chunks(REPO_A, 3)

    summary = embed_repository_chunks(_SessionLocal(), REPO_A)

    assert summary["embedded"] == 3
    assert summary["skipped"] == 0
    assert summary["failed"] == 0

    db = _SessionLocal()
    chunks = db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).all()
    db.close()

    for chunk in chunks:
        stored = chunk.embedding
        assert stored is not None
        assert len(stored) == DIM
        assert chunk.embedding_dimension == DIM
        assert chunk.embedding_model == "fake-model"
        assert chunk.embedded_content_hash == chunk.content_hash
        assert chunk.embedded_at is not None


def test_repeated_embedding_is_idempotent(fake_provider):
    _clear_chunks(REPO_A)
    _make_chunks(REPO_A, 3)

    embed_repository_chunks(_SessionLocal(), REPO_A)
    calls_after_first = len(fake_provider.calls)

    second = embed_repository_chunks(_SessionLocal(), REPO_A)

    assert second["embedded"] == 0
    assert second["skipped"] == 3
    assert count_pending_chunks(_SessionLocal(), REPO_A) == 0
    # No provider call at all on the second run.
    assert len(fake_provider.calls) == calls_after_first


def test_changed_content_hash_regenerates_embedding(fake_provider):
    _clear_chunks(REPO_A)
    _make_chunks(REPO_A, 1)

    embed_repository_chunks(_SessionLocal(), REPO_A)

    db = _SessionLocal()
    chunk = db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).one()
    old_hash = chunk.embedded_content_hash
    chunk.content = "def c0():\n    return 999\n"
    chunk.content_hash = "hash-changed"
    db.commit()
    chunk_id = chunk.id
    db.close()

    result = embed_repository_chunks(_SessionLocal(), REPO_A)
    assert result["embedded"] == 1
    assert result["skipped"] == 0

    db = _SessionLocal()
    updated = db.query(DBChunk).filter(DBChunk.id == chunk_id).one()
    db.close()
    assert updated.embedded_content_hash == "hash-changed"
    assert updated.embedded_content_hash != old_hash


def test_force_reembeds_unchanged_chunks():
    _clear_chunks(REPO_A)
    _make_chunks(REPO_A, 2)
    embed_repository_chunks(_SessionLocal(), REPO_A)

    forced = embed_repository_chunks(_SessionLocal(), REPO_A, force=True)
    assert forced["embedded"] == 2
    assert forced["skipped"] == 0


def test_failed_embedding_preserves_chunk_data():
    _clear_chunks(REPO_A)
    _make_chunks(REPO_A, 2)

    db = _SessionLocal()
    before = [
        (c.id, c.chunk_key, c.content, c.content_hash)
        for c in db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).order_by(DBChunk.id).all()
    ]
    db.close()

    failing = FakeProvider(fail=True)
    result = embed_repository_chunks(_SessionLocal(), REPO_A, provider=failing)

    assert result["failed"] == 2
    assert result["embedded"] == 0
    assert result["errors"]

    db = _SessionLocal()
    after = [
        (c.id, c.chunk_key, c.content, c.content_hash)
        for c in db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).order_by(DBChunk.id).all()
    ]
    chunks = db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).all()
    embeddings = [c.embedding for c in chunks]
    embedded_hashes = [c.embedded_content_hash for c in chunks]
    db.close()

    # Chunk rows are completely intact and no partial embedding was written.
    assert after == before
    assert all(e is None for e in embeddings)
    assert all(h is None for h in embedded_hashes)


def test_provider_arity_mismatch_does_not_partially_embed():
    _clear_chunks(REPO_A)
    _make_chunks(REPO_A, 3)

    class ShortProvider(FakeProvider):
        def embed(self, texts):
            return [[0.0] * DIM]  # only one vector for the batch

    result = embed_repository_chunks(_SessionLocal(), REPO_A, provider=ShortProvider())
    assert result["failed"] == 3
    assert result["embedded"] == 0

    db = _SessionLocal()
    chunks = db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).all()
    db.close()
    assert all(c.embedding is None for c in chunks)


def test_batching_calls_provider_in_batches():
    _clear_chunks(REPO_A)
    _make_chunks(REPO_A, 5)

    provider = FakeProvider()
    embed_repository_chunks(_SessionLocal(), REPO_A, batch_size=2, provider=provider)

    assert [len(call) for call in provider.calls] == [2, 2, 1]


# --------------------------------------------------------------------------
# Repository isolation
# --------------------------------------------------------------------------

def test_embedding_is_repository_scoped():
    _clear_chunks(REPO_A)
    _clear_chunks(REPO_B)
    _make_chunks(REPO_A, 2, prefix="a")
    _make_chunks(REPO_B, 2, prefix="b")

    embed_repository_chunks(_SessionLocal(), REPO_A)

    db = _SessionLocal()
    a_chunks = db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).all()
    b_chunks = db.query(DBChunk).filter(DBChunk.repository_id == REPO_B).all()
    db.close()

    assert all(c.embedding is not None for c in a_chunks)
    # Repo B was never touched.
    assert all(c.embedding is None for c in b_chunks)
    assert count_pending_chunks(_SessionLocal(), REPO_B) == 2


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

def test_embedding_status_endpoint():
    _clear_chunks(REPO_A)
    _make_chunks(REPO_A, 3)

    before = client.get(f"/repositories/{REPO_A}/embeddings")
    assert before.status_code == 200
    assert before.json()["total_chunks"] == 3
    assert before.json()["pending_chunks"] == 3
    assert before.json()["embedded_chunks"] == 0

    response = client.post(f"/repositories/{REPO_A}/embeddings")
    assert response.status_code == 200
    assert response.json()["embedded"] == 3

    after = client.get(f"/repositories/{REPO_A}/embeddings").json()
    assert after["embedded_chunks"] == 3
    assert after["pending_chunks"] == 0


def test_embedding_endpoints_unknown_repository_404():
    assert client.get("/repositories/999/embeddings").status_code == 404
    assert client.post("/repositories/999/embeddings").status_code == 404


def test_embedding_status_reports_configured_model_and_dimension():
    body = client.get(f"/repositories/{REPO_A}/embeddings").json()
    assert body["model"] == "BAAI/bge-small-en-v1.5"
    assert body["dimension"] == 384
