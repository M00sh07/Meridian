import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from main import app
from models import Repository, File, Chunk
from services.embedding_provider import EmbeddingProvider, set_provider

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
            # simple deterministic mock vector based on text content
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
def test_data():
    from database import SessionLocal
    import uuid
    db_session = SessionLocal()

    uid = uuid.uuid4().hex
    repo1 = Repository(url=f"https://github.com/test/repo1-{uid}", status="completed")
    repo2 = Repository(url=f"https://github.com/test/repo2-{uid}", status="completed")
    db_session.add(repo1)
    db_session.add(repo2)
    db_session.commit()
    db_session.refresh(repo1)
    db_session.refresh(repo2)

    repo1_id = repo1.id
    repo2_id = repo2.id

    file1 = File(repository_id=repo1_id, path="src/auth.py", language="python")
    file2 = File(repository_id=repo1_id, path="src/db.py", language="python")
    file3 = File(repository_id=repo2_id, path="src/auth.py", language="python")
    db_session.add_all([file1, file2, file3])
    db_session.commit()
    db_session.refresh(file1)
    db_session.refresh(file2)
    db_session.refresh(file3)

    # repo 1 chunks
    chunk1 = Chunk(
        repository_id=repo1_id,
        file_id=file1.id,
        chunk_key="c1",
        chunk_type="function",
        path="src/auth.py",
        symbol_name="login",
        language="python",
        content="def login(): pass # authentication",
        content_hash="h1",
        embedding=[0.9, 0.1, 0.0],
        embedded_content_hash="h1"
    )
    chunk2 = Chunk(
        repository_id=repo1_id,
        file_id=file2.id,
        chunk_key="c2",
        chunk_type="class",
        path="src/db.py",
        symbol_name="Database",
        language="python",
        content="class Database: pass # database connection",
        content_hash="h2",
        embedding=[0.1, 0.9, 0.0],
        embedded_content_hash="h2"
    )
    chunk3 = Chunk(
        repository_id=repo1_id,
        file_id=file1.id,
        chunk_key="c3",
        chunk_type="function",
        path="src/auth.py",
        symbol_name="logout",
        language="python",
        content="def logout(): pass # other",
        content_hash="h3",
        embedding=[0.0, 0.1, 0.9],
        embedded_content_hash="h3"
    )

    # repo 2 chunk (should be isolated)
    chunk4 = Chunk(
        repository_id=repo2_id,
        file_id=file3.id,
        chunk_key="c4",
        chunk_type="function",
        path="src/auth.py",
        symbol_name="login",
        language="python",
        content="def login(): pass # authentication repo2",
        content_hash="h4",
        embedding=[0.95, 0.05, 0.0],
        embedded_content_hash="h4"
    )

    # unembedded chunk
    chunk5 = Chunk(
        repository_id=repo1_id,
        file_id=file1.id,
        chunk_key="c5",
        chunk_type="module",
        path="src/utils.py",
        language="python",
        content="some utils",
        content_hash="h5",
        embedding=None
    )

    db_session.add_all([chunk1, chunk2, chunk3, chunk4, chunk5])
    db_session.commit()

    db_session.close()

    return {"repo1_id": repo1_id, "repo2_id": repo2_id}

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    from database import Base, engine, SessionLocal
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_semantic_ranking(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    # query that yields [1.0, 0.0, 0.0] from our mock provider
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
    repo2_id = test_data["repo2_id"]
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
    assert data["total"] == 3  # total is 3 matching chunks for this repo

def test_no_embeddings(test_data, mock_embedding_provider):
    # delete all embeddings in repo 1
    from database import SessionLocal
    db = SessionLocal()
    chunks = db.query(Chunk).filter(Chunk.repository_id == test_data["repo1_id"]).all()
    for c in chunks:
        c.embedding = None
    db.commit()
    db.close()

    response = client.get(f"/repositories/{test_data['repo1_id']}/search?q=test")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 0

def test_unknown_repository(mock_embedding_provider):
    response = client.get(f"/repositories/999/search?q=test")
    assert response.status_code == 404

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
