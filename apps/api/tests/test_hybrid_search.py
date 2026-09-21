"""Hybrid/lexical search behaviour tests.

The `test_data` and `mock_embedding_provider` fixtures are reused from
 test_search.py; `test_data` itself delegates to conftest's `search_test_data`.
"""
import os
import pytest
from fastapi.testclient import TestClient
from main import app
from models import Chunk
from services.search.tokenizer import tokenize
from tests.test_search import test_data, mock_embedding_provider
# conftest.py overrides the app's get_db dependency with the temporary engine.
client = TestClient(app)


def test_tokenizer():
    assert set(tokenize("payment_retry")) == {"payment", "retry"}
    assert set(tokenize("PaymentRetryService")) == {"payment", "retry", "service"}
    assert set(tokenize("payments/retry.py")) == {"payments", "retry", "py"}
    assert set(tokenize("payment retry logic")) == {"payment", "retry", "logic"}


def test_explicit_semantic_mode(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=authentication&mode=semantic")
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 3
    assert "semantic_score" in results[0]
    assert results[0]["lexical_score"] == 0.0


def test_explicit_lexical_mode(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=database&mode=lexical")
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) >= 1
    assert results[0]["symbol_name"] == "Database"
    assert results[0]["lexical_score"] > 0
    assert results[0]["semantic_score"] == 0.0


def test_invalid_mode(test_data):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=auth&mode=invalid")
    assert response.status_code == 422


def test_hybrid_ranking_combines_signals(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=authentication&mode=hybrid")
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["semantic_score"] > 0
    assert results[0]["lexical_score"] > 0


def test_no_embeddings_lexical_works(test_data, mock_embedding_provider, TestingSessionLocal):
    db = TestingSessionLocal()
    chunks = db.query(Chunk).filter(Chunk.repository_id == test_data["repo1_id"]).all()
    for c in chunks:
        c.embedding = None
    db.commit()
    db.close()


    response = client.get(f"/repositories/{test_data['repo1_id']}/search?q=database&mode=hybrid")
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) > 0
    assert results[0]["symbol_name"] == "Database"
    assert results[0]["lexical_score"] > 0
    assert results[0]["semantic_score"] == 0.0


def test_total_semantics(test_data, mock_embedding_provider):
    repo_id = test_data["repo1_id"]

    response = client.get(f"/repositories/{repo_id}/search?q=test&mode=semantic")
    assert response.json()["total"] == 3

    response = client.get(f"/repositories/{repo_id}/search?q=test&mode=lexical")
    assert response.json()["total"] == 4

    response = client.get(f"/repositories/{repo_id}/search?q=test&mode=hybrid")
    assert response.json()["total"] == 4


def test_camel_case_pascal_case_scoring():
    from services.search.lexical_search import score_lexical

    c = Chunk(symbol_name="PaymentRetryService", path="src/payments.py", content="class PaymentRetryService:")
    query = "PaymentRetryService"
    q_tokens = tokenize(query)
    score = score_lexical(query, q_tokens, c)
    assert score == 1.0

    query2 = "payment retry"
    q2_tokens = tokenize(query2)
    score2 = score_lexical(query2, q2_tokens, c)
    assert score2 > 0.0


def test_deterministic_tie_ordering(test_data, mock_embedding_provider, TestingSessionLocal):
    db = TestingSessionLocal()
    repo_id = test_data["repo1_id"]

    c1 = Chunk(repository_id=repo_id, chunk_key="tie1", content_hash="th1", chunk_type="tie", path="a.py", start_line=1, content="tiebreaker", embedding=[0.1]*384)
    c2 = Chunk(repository_id=repo_id, chunk_key="tie2", content_hash="th2", chunk_type="tie", path="a.py", start_line=2, content="tiebreaker", embedding=[0.1]*384)
    c3 = Chunk(repository_id=repo_id, chunk_key="tie3", content_hash="th3", chunk_type="tie", path="b.py", start_line=1, content="tiebreaker", embedding=[0.1]*384)
    db.add_all([c3, c2, c1])
    db.commit()

    response = client.get(f"/repositories/{repo_id}/search?q=tiebreaker&mode=hybrid")
    assert response.status_code == 200
    results = response.json()["results"]

    tie_results = [r for r in results if r["chunk_type"] == "tie"]
    assert len(tie_results) == 3
    assert tie_results[0]["path"] == "a.py" and tie_results[0]["start_line"] == 1
    assert tie_results[1]["path"] == "a.py" and tie_results[1]["start_line"] == 2
    assert tie_results[2]["path"] == "b.py" and tie_results[2]["start_line"] == 1
    db.close()


def test_candidate_limiting_exact_match(test_data, mock_embedding_provider, TestingSessionLocal):
    db = TestingSessionLocal()
    repo_id = test_data["repo1_id"]

    chunks = []
    for i in range(10):
        chunks.append(Chunk(repository_id=repo_id, chunk_key=f"wk_{i}", content_hash=f"wh_{i}", chunk_type="limit_test", path=f"weak_{i}.py", content="needle match", embedding=[0.0]*384))
    chunks.append(Chunk(repository_id=repo_id, chunk_key="ex", content_hash="exh", chunk_type="limit_test", path="exact.py", symbol_name="Needle", content="some content", embedding=[0.0]*384))
    db.add_all(chunks)
    db.commit()

    os.environ["HYBRID_CANDIDATE_MULTIPLIER"] = "2"
    try:
        response = client.get(f"/repositories/{repo_id}/search?q=Needle&limit=2&mode=lexical")
        assert response.status_code == 200
        results = response.json()["results"]
        assert any(r["symbol_name"] == "Needle" for r in results)
    finally:
        os.environ.pop("HYBRID_CANDIDATE_MULTIPLIER", None)
        db.close()


def test_empty_query(test_data):
    repo_id = test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/search?q=   ")
    assert response.status_code == 400
