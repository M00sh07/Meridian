"""Semantic / hybrid search API tests.

All repository and chunk rows come from the `search_test_data` fixture in
conftest.py, which allocates ids from the database and cleans up after itself.
No test in this module hardcodes a repository id.
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from models import Chunk
from services.embedding_provider import EmbeddingProvider, set_provider
# conftest.py overrides the app's get_db dependency with the temporary engine.
client = TestClient(app)


class MockProvider(EmbeddingProvider):
    def __init__(self, dimension=3):
        self._dimension = dimension
        self.calls = []

    @property
    def model_name(self) -> str:
        return "mock-model"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        results = []
        for text in texts:
            if "authentication" in text.lower():
                results.append([1.0, 0.0, 0.0])
            elif "database" in text.lower():
                results.append([0.0, 1.0, 0.0])
            else:
                results.append([0.0, 0.0, 1.0])
        return results


@pytest.fixture
def mock_embedding_provider():
    provider = MockProvider(dimension=3)
    set_provider(provider)
    yield provider
    set_provider(None)


@pytest.fixture
def test_data(search_test_data):
    """Shared isolated search fixture, re-exported under this module's name.

    test_hybrid_search.py and test_context_assembly.py import `test_data` from
    here, so the fixture is defined (not the rows) in one place: conftest.py.
    """
    return search_test_data

def test_search_fixture_ids_are_database_allocated(test_data):
    """Repository ids come from the database, never from hardcoded literals."""
    assert isinstance(test_data["repo1_id"], int)
    assert isinstance(test_data["repo2_id"], int)
    assert test_data["repo1_id"] != test_data["repo2_id"]


def test_semantic_ranking(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=authentication")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "authentication"
    results = data["results"]
    assert len(results) == 3  # out of 3 embedded chunks in repo1

    assert results[0]["chunk_type"] == "function"
    assert results[1]["chunk_type"] == "class"
    assert results[2]["chunk_type"] == "function"
    assert results[0]["similarity"] > results[1]["similarity"]
    assert results[1]["similarity"] > results[2]["similarity"]


def test_repository_isolation(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=authentication")
    results = response.json()["results"]
    for r in results:
        assert "repo2" not in r["content"]


def test_chunk_type_filter(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=authentication&chunk_type=class")
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["chunk_type"] == "class"


def test_language_filter(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=authentication&language=typescript")
    results = response.json()["results"]
    assert len(results) == 0

    response = client.get(f"/repositories/{repo_id}/search?q=authentication&language=python")
    results = response.json()["results"]
    assert len(results) == 3


def test_path_filter(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=authentication&path=src/db.py")
    results = response.json()["results"]
    assert len(results) == 1
    assert "src/db.py" == results[0]["path"]


def test_symbol_name_filter(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=authentication&symbol_name=logout")
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["symbol_name"] == "logout"


def test_empty_query(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=   ")
    assert response.status_code == 400


def test_limit_validation(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=test&limit=0")
    assert response.status_code == 422
    response = client.get(f"/repositories/{repo_id}/search?q=test&limit=100")
    assert response.status_code == 422
    response = client.get(f"/repositories/{repo_id}/search?q=test&limit=2")
    data = response.json()
    assert len(data["results"]) == 2
    assert data["total"] == 4  # total is 4 matching chunks for this repo in hybrid mode


def test_no_embeddings(test_data, mock_embedding_provider, TestingSessionLocal):
    db = TestingSessionLocal()
    chunks = db.query(Chunk).filter(Chunk.repository_id == test_data["repo1_id"]).all()
    for c in chunks:
        c.embedding = None
    db.commit()
    db.close()

    response = client.get(f"/repositories/{test_data['repo1_id']}/search?q=test")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 0

def test_unknown_repository_is_scoped(mock_embedding_provider, TestingSessionLocal):
    """An unknown repository id must 404, and must not match fixture data.

    This replaces the previous hardcoded `/repositories/999/search` call so the
    outcome cannot depend on which ids happen to exist in the database.
    """
    from models import Repository
    db = TestingSessionLocal()
    known_ids = {row.id for row in db.query(Repository.id).all()}
    db.close()

    unknown_id = max(known_ids) + 1 if known_ids else 1
    assert unknown_id not in known_ids
    assert client.get(f"/repositories/{unknown_id}/search?q=test").status_code == 404


def test_api_response_shape(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=test")
    data = response.json()
    assert "query" in data
    assert "results" in data
    assert "total" in data

    if len(data["results"]) > 0:
        result = data["results"][0]
        assert "chunk_id" in result
        assert "path" in result
        assert "chunk_type" in result
        assert "symbol_name" in result
        assert "language" in result
        assert "start_line" in result
        assert "end_line" in result
        assert "content" in result
        assert "similarity" in result
