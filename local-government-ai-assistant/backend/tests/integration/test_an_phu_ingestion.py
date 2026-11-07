"""An Phú ingestion checks (Phase 10).

Simulated tests run against a temporary Chroma store and need no embedding
model (vectors are random). The real-corpus test is marked
``real_ingestion`` and is deselected by default via pytest addopts; run it
with ``pytest -m real_ingestion``.
"""

import numpy as np
import pytest

from app.core.config import settings
from app.database.vector_store import VectorStore
from app.models.data_models import Chunk
from app.rag.retrieval.index_manager import rebuild_bm25_index

AN_PHU_DOCS = ["an_phu_2454", "an_phu_2788", "an_phu_2838"]
CENTRAL_DOC = "151-2025-ND-CP"


def _seed_chunks():
    specs = [
        ("an_phu_2454", "local", "Nghị quyết thành lập Ban kinh tế - Ngân sách của HĐND phường An Phú."),
        ("an_phu_2788", "local", "Quy chế tiếp công dân của HĐND phường An Phú."),
        ("an_phu_2838", "local", "Quy chế tiếp công dân, tiếp nhận, phân loại, xử lý đơn của HĐND phường."),
        (CENTRAL_DOC, "central", "Nghị định quy định về đăng ký hộ tịch."),
    ]
    chunks = [
        Chunk(
            text=text,
            document_id=document_id,
            chunk_index=0,
            metadata={"doc_scope": scope},
        )
        for document_id, scope, text in specs
    ]
    embeddings = np.random.randn(len(chunks), 768).astype(np.float32)
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    return chunks, embeddings


@pytest.fixture
def temp_store(tmp_path):
    """Chroma store on a temporary directory (never the production DB)."""
    return VectorStore(persist_directory=str(tmp_path / "chroma"))


def test_simulated_an_phu_documents_ingest(temp_store):
    """Three simulated An Phú documents plus one national document ingest cleanly."""
    chunks, embeddings = _seed_chunks()
    temp_store.add_chunks(
        chunks,
        embeddings,
        filename="seed.pdf",
        extra_metadata={"locality_code": "25975"},
    )

    assert temp_store.get_collection_stats()["count"] == 4
    for chunk in chunks:
        result = temp_store.collection.get(ids=[f"{chunk.document_id}_0"])
        assert result["ids"], f"missing chunk for {chunk.document_id}"
        metadata = result["metadatas"][0]
        assert metadata["doc_scope"] == chunk.metadata["doc_scope"]
        assert metadata["locality_code"] == "25975"


def test_simulated_query_local_vs_global_filter(temp_store):
    """Querying with a doc_scope filter returns the matching corpus only."""
    chunks, embeddings = _seed_chunks()
    temp_store.add_chunks(chunks, embeddings, filename="seed.pdf")

    query = np.random.randn(768).astype(np.float32)
    query = query / np.linalg.norm(query)

    local_hits = temp_store.search(query, k=10, where={"doc_scope": "local"})
    assert {hit.metadata["document_id"] for hit in local_hits} == set(AN_PHU_DOCS)

    central_hits = temp_store.search(query, k=10, where={"doc_scope": "central"})
    assert {hit.metadata["document_id"] for hit in central_hits} == {CENTRAL_DOC}


def test_bm25_rebuild_matches_chroma(temp_store, tmp_path):
    """Rebuilt BM25 corpus size equals the Chroma chunk count."""
    chunks, embeddings = _seed_chunks()
    temp_store.add_chunks(chunks, embeddings, filename="seed.pdf")

    index = rebuild_bm25_index(
        vector_store=temp_store,
        persist_dir=tmp_path / "bm25",
    )

    assert index is not None
    assert len(index.corpus_tokens) == temp_store.get_collection_stats()["count"]


@pytest.mark.real_ingestion
def test_real_an_phu_corpus_has_doc_scope():
    """Production corpus: no chunk without doc_scope and An Phú docs are local."""
    store = VectorStore(persist_directory=settings.chroma_db_path)
    stats = store.get_collection_stats()
    assert stats["count"] > 0

    metadatas = store.collection.get(include=["metadatas"])["metadatas"]
    empty_scope = [m for m in metadatas if not (m.get("doc_scope") or "")]
    assert empty_scope == [], f"{len(empty_scope)} chunks missing doc_scope"

    an_phu_local = [
        m
        for m in metadatas
        if str(m.get("document_id") or "").startswith("an_phu_")
        and m.get("doc_scope") == "local"
    ]
    assert len(an_phu_local) >= 2000
