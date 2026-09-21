"""Context assembly API tests.

Uses the shared `test_data` fixture from test_search.py, which delegates to
conftest's `search_test_data`, so no repository id is hardcoded here.
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from tests.test_search import test_data, mock_embedding_provider
from models import Chunk
# conftest.py overrides the app's get_db dependency with the temporary engine.
client = TestClient(app)


def test_context_assembly_basic(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/context?q=database")

    assert response.status_code == 200
    data = response.json()

    assert data["query"] == "database"
    assert data["repository_id"] == repo_id
    assert "files" in data
    assert data["total_chunks"] > 0
    assert data["total_characters"] > 0

    files = data["files"]
    assert len(files) > 0
    assert files[0]["path"] == "src/db.py"

    first_chunk = files[0]["chunks"][0]
    assert "chunk_id" in first_chunk
    assert "content" in first_chunk
    assert "score" in first_chunk
    assert "semantic_score" in first_chunk
    assert "lexical_score" in first_chunk
    assert "symbol_name" in first_chunk


def test_context_budget(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/context?q=test&budget=30")
    assert response.status_code == 200
    data = response.json()
    assert data["total_characters"] <= 30

    response_no_budget = client.get(f"/repositories/{repo_id}/context?q=test")
    data_no_budget = response_no_budget.json()
    assert data_no_budget["total_characters"] > data["total_characters"]


def test_context_deduplication(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/context?q=test")
    assert response.status_code == 200
    data = response.json()

    seen_ids = set()
    for f in data["files"]:
        for c in f["chunks"]:
            assert c["chunk_id"] not in seen_ids
            seen_ids.add(c["chunk_id"])


def test_context_unknown_repository(test_data, TestingSessionLocal):
    """An unknown repository id must 404 rather than return another repo data.

    The id is derived from the database instead of being a hardcoded literal, so
    the assertion cannot accidentally match a real repository.
    """
    from models import Repository
    db = TestingSessionLocal()
    known_ids = {row.id for row in db.query(Repository.id).all()}
    db.close()

    unknown_id = max(known_ids) + 1 if known_ids else 1
    assert unknown_id not in known_ids
    response = client.get(f"/repositories/{unknown_id}/context?q=test")
    assert response.status_code == 404


def test_context_metadata_filters(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/context?q=test&chunk_type=function")
    assert response.status_code == 200
    data = response.json()

    for f in data["files"]:
        for c in f["chunks"]:
            assert c["chunk_type"] == "function"


def test_context_missing_embeddings(test_data, mock_embedding_provider, TestingSessionLocal):
    repo_id = test_data["repo1_id"]

    db = TestingSessionLocal()
    chunks = db.query(Chunk).filter(Chunk.repository_id == repo_id).all()
    for c in chunks:
        c.embedding = None
    db.commit()
    db.close()

    response = client.get(f"/repositories/{repo_id}/context?q=database&mode=hybrid")
    assert response.status_code == 200
    data = response.json()

    assert data["total_chunks"] > 0
    assert data["files"][0]["chunks"][0]["symbol_name"] == "Database"
    assert data["files"][0]["chunks"][0]["semantic_score"] == 0.0
    assert data["files"][0]["chunks"][0]["lexical_score"] > 0.0


def test_context_empty_results(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/context?q=nonexistent_string_12345&mode=lexical")
    assert response.status_code == 200
    data = response.json()
    assert data["total_chunks"] == 0
    assert data["total_characters"] == 0
    assert len(data["files"]) == 0
