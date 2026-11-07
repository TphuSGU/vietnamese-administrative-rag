"""
Hybrid Retriever: Combines Dense (Vector) + Sparse (BM25) Search.

Hybrid search combines:
1. Dense retrieval: Semantic similarity (vector embeddings)
2. Sparse retrieval: Keyword matching (BM25)

Fusion method: Reciprocal Rank Fusion (RRF)
- Paper: "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods"
- Formula: RRF_score(d) = sum(1 / (k + rank_i(d))) for all rankings i
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from pathlib import Path

from app.rag.retrieval.retriever import Retriever
from app.rag.retrieval.bm25s_index import BM25SIndex
from app.rag.retrieval.query_constraints import (
    QueryConstraints,
    filter_candidates_by_constraints,
    parse_query_constraints,
)
from app.rag.retrieval.context_intent import (
    filter_schedule_candidates,
    parse_context_intent,
)
from app.rag.ingestion.procedure_metadata import (
    normalize_for_match,
    procedure_title_score,
)
from app.rag.embedding.embedding_service import EmbeddingService
from app.database.vector_store import VectorStore
from app.models.data_models import RetrievedChunk, SearchResult
from app.core.logging import get_logger

logger = get_logger(__name__)


def _where_clauses(where: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not where:
        return []
    if set(where) == {"$and"}:
        return list(where.get("$and") or [])
    return [{key: value} for key, value in where.items()]


def _combine_where(*parts: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    clauses: List[Dict[str, Any]] = []
    for part in parts:
        clauses.extend(_where_clauses(part))
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


class HybridRetriever(Retriever):
    """
    Hybrid retrieval combining dense and sparse methods.
    
    Architecture:
    Query → [Vector Search] ──┐
            [BM25 Search]   ──┤→ [RRF Fusion] → Top-K Results
    
    Benefits:
    - Vector: Captures semantic meaning, synonyms, paraphrasing
    - BM25: Captures exact terms, proper nouns, technical terms
    - RRF: Combines rankings without score normalization issues
    
    Validates: Enhanced Requirements 8.1-8.6
    """
    
    # RRF constant (recommended value from paper)
    RRF_K = 60
    
    # Cosine-similarity threshold applied to vector candidates before fusion.
    # NOTE: RRF scores (~1/60) and cross-encoder logits use a different scale,
    # so this value must NOT be applied to fused/reranked results.
    MIN_SIMILARITY_THRESHOLD = 0.25

    # Over-fetch before metadata filtering; exact doc numbers are often outside
    # the default top-k when many documents share "NQ" / "HĐND".
    CANDIDATE_MULTIPLIER = 20
    MAX_CANDIDATES = 300
    LOCALITY_BOOST = 0.002
    QUERY_KEYWORD_BOOST = 0.01
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        alpha: float = 0.6,
        min_similarity: float = MIN_SIMILARITY_THRESHOLD,
        use_reranking: bool = False,
        bm25s_persist_dir: Optional[str] = None
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            embedding_service: Embedding service for vector search
            vector_store: Vector store for similarity search
            alpha: Weight for vector search (0-1)
                   0.6 = 60% weight on semantic, 40% on keyword
                   Recommended: 0.5-0.7 for balanced retrieval
            min_similarity: Minimum similarity score threshold
            use_reranking: Whether to apply cross-encoder reranking
            bm25s_persist_dir: Directory to persist BM25S index
        """
        super().__init__(embedding_service, vector_store)
        # Persistence is opt-in: tests and ad-hoc instances must never
        # overwrite the production BM25 index on disk.
        self.bm25_index = BM25SIndex(
            persist_dir=Path(bm25s_persist_dir) if bm25s_persist_dir else None
        )
        self.alpha = alpha
        self.min_similarity = min_similarity
        self.use_reranking = use_reranking
        
        # Initialize reranker if enabled (will be set later)
        self.reranker = None
        self._procedure_chunks_cache: Dict[str, List[RetrievedChunk]] = {}
        if use_reranking:
            # Lazy loading - import only if needed
            from app.rag.retrieval.reranker import Reranker
            self.reranker = Reranker()
        
        logger.info(
            "HybridRetriever initialized with BM25S",
            extra={
                "alpha": alpha,
                "min_similarity": min_similarity,
                "rrf_k": self.RRF_K,
                "reranking_enabled": use_reranking,
                "bm25s_persist_dir": bm25s_persist_dir
            }
        )
    
    def index_documents(self, chunks: List[RetrievedChunk]) -> None:
        """
        Build BM25S index for hybrid search.
        
        Call this after documents are loaded into vector store.
        Index is automatically saved to disk if persistence is enabled.
        
        Args:
            chunks: All chunks that have been indexed
        """
        logger.info(f"Building BM25S index for {len(chunks)} chunks")
        self.bm25_index.index_chunks(chunks)
        logger.info("BM25S index ready for hybrid search")
    
    def retrieve(
        self,
        query: str,
        k: int = 5,
        locality_code: Optional[str] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """
        Hybrid retrieval with RRF fusion + legal metadata constraints.

        Exact document numbers and single-year constraints are applied after
        over-fetching. Local documents get a small locality boost, but global
        documents remain available as fallback.
        """
        if k < self.MIN_K or k > self.MAX_K:
            raise ValueError(
                f"K must be between {self.MIN_K} and {self.MAX_K}, got {k}"
            )

        constraints = parse_query_constraints(query)
        intent = parse_context_intent(query)
        candidate_k = min(
            max(k * self.CANDIDATE_MULTIPLIER, 100),
            self.MAX_CANDIDATES,
        )
        locality_filter = (
            {"locality_code": str(locality_code)} if locality_code else None
        )
        intent_filter = (
            {"doc_type": intent.doc_type}
            if intent.doc_type and not constraints.has_doc_number
            else None
        )
        local_where = _combine_where(where, locality_filter, intent_filter)
        global_where = _combine_where(where, intent_filter)

        logger.info(
            "Hybrid retrieval started",
            extra={
                "query": query[:50],
                "k": k,
                "candidate_k": candidate_k,
                "alpha": self.alpha,
                "threshold": self.min_similarity,
                "doc_numbers": sorted(constraints.doc_numbers),
                "years": sorted(constraints.years),
                "locality_code": locality_code,
                "intent": intent.kind or "legal",
                "schedule_periods": sorted(intent.periods),
            }
        )

        local_candidates = self._search_candidates(
            query, candidate_k, local_where or None
        )
        global_candidates = (
            self._search_candidates(query, candidate_k, global_where or None)
            if local_where
            else local_candidates
        )

        if intent.is_schedule and intent.periods:
            local_candidates = filter_schedule_candidates(
                local_candidates, intent.periods
            )
            global_candidates = filter_schedule_candidates(
                global_candidates, intent.periods
            )
            if not local_candidates and not global_candidates:
                logger.info(
                    "No schedule matched requested period",
                    extra={"periods": sorted(intent.periods)},
                )
                return []

        if intent.is_procedure and locality_code and not constraints.has_doc_number:
            title_candidates = self._procedure_title_candidates(
                query, locality_code
            )
            fact_candidates = self._procedure_fact_candidates(
                query, locality_code, title_candidates
            )
            local_candidates = self._dedupe(
                local_candidates + title_candidates + fact_candidates
            )

        exact_candidates: List[RetrievedChunk] = []
        if constraints.has_doc_number:
            exact_candidates = self._exact_doc_candidates(
                locality_code, constraints
            )

        combined = self._dedupe(
            exact_candidates + local_candidates + global_candidates
        )
        filtered = filter_candidates_by_constraints(combined, constraints)
        if filtered:
            combined = filtered

        if locality_code:
            for chunk in combined:
                if str(chunk.metadata.get("locality_code") or "") == str(locality_code):
                    chunk.similarity_score += self.LOCALITY_BOOST

        # "sáp nhập" questions often rank table/prose chunks below generic
        # documents that merely mention the ward. Boost chunks whose own text
        # names the requested operation.
        query_norm = normalize_for_match(query)
        if "sap nhap" in query_norm:
            for chunk in combined:
                if "sap nhap" in normalize_for_match(chunk.text or ""):
                    chunk.similarity_score += self.QUERY_KEYWORD_BOOST

        # Procedure names often contain the same prefix. Rank the shortest
        # matching title first ("Đăng ký khai sinh" before "… lưu động").
        if intent.is_procedure and not constraints.has_doc_number:
            combined.sort(
                key=lambda chunk: (
                    procedure_title_score(query, chunk.metadata or {}),
                    chunk.similarity_score,
                ),
                reverse=True,
            )
            combined = self._limit_per_document(combined, max_per_document=2)
        else:
            combined.sort(key=lambda chunk: chunk.similarity_score, reverse=True)

        # Keep exact doc-number queries deterministic; reranking otherwise may
        # move a prose-similar wrong document above the requested number.
        if self.reranker and combined and not constraints.has_doc_number:
            logger.debug("Applying cross-encoder reranking")
            rerank_k = min(max(k * 2, k), len(combined))
            combined = self.reranker.rerank(query, combined, top_k=rerank_k)
            if locality_code:
                for chunk in combined:
                    if str(chunk.metadata.get("locality_code") or "") == str(locality_code):
                        chunk.similarity_score += self.LOCALITY_BOOST
                combined.sort(key=lambda chunk: chunk.similarity_score, reverse=True)

        final_results = combined[:k]
        logger.info(
            "Hybrid retrieval completed",
            extra={
                "local_candidates": len(local_candidates),
                "global_candidates": len(global_candidates),
                "exact_candidates": len(exact_candidates),
                "combined_count": len(combined),
                "final_count": len(final_results),
                "intent": intent.kind or "legal",
                "top_score": final_results[0].similarity_score if final_results else 0,
            }
        )
        return final_results

    def _search_candidates(
        self,
        query: str,
        candidate_k: int,
        where: Optional[Dict[str, Any]],
    ) -> List[RetrievedChunk]:
        query_embedding = self.embedding_service.embed_single(query)
        if not isinstance(query_embedding, np.ndarray):
            query_embedding = np.asarray(query_embedding)

        search_results: List[SearchResult] = self.vector_store.search(
            query_embedding,
            k=candidate_k,
            where=where,
        )
        vector_results = [
            RetrievedChunk(
                text=result.text,
                similarity_score=result.similarity_score,
                metadata=result.metadata,
            )
            for result in search_results
            if result.similarity_score >= self.min_similarity
        ]

        bm25_results = self.bm25_index.search(query, k=candidate_k)
        if where:
            bm25_results = [
                (chunk, score)
                for chunk, score in bm25_results
                if self._matches_where(chunk.metadata, where)
            ]

        return self._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            k=candidate_k,
        )

    @staticmethod
    def _matches_where(metadata: Dict[str, Any], where: Dict[str, Any]) -> bool:
        if not where:
            return True
        if "$and" in where:
            return all(
                HybridRetriever._matches_where(metadata, clause)
                for clause in where.get("$and") or []
            )
        if "$or" in where:
            return any(
                HybridRetriever._matches_where(metadata, clause)
                for clause in where.get("$or") or []
            )
        for key, value in where.items():
            if key.startswith("$"):
                continue
            if metadata.get(key) != value:
                return False
        return True

    @staticmethod
    def _dedupe(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        positions: Dict[Tuple[Any, ...], int] = {}
        output: List[RetrievedChunk] = []
        for chunk in chunks:
            metadata = chunk.metadata or {}
            key = (
                metadata.get("document_id"),
                metadata.get("chunk_index"),
                chunk.text[:80],
            )
            if key in positions:
                position = positions[key]
                if chunk.similarity_score > output[position].similarity_score:
                    output[position] = chunk
                continue
            positions[key] = len(output)
            output.append(chunk)
        return output

    @staticmethod
    def _limit_per_document(
        chunks: List[RetrievedChunk],
        max_per_document: int = 2,
    ) -> List[RetrievedChunk]:
        """Keep procedure context diverse without dropping all chunks of a doc."""
        counts: Dict[str, int] = {}
        output: List[RetrievedChunk] = []
        for chunk in chunks:
            document_id = str((chunk.metadata or {}).get("document_id") or "")
            if document_id:
                if counts.get(document_id, 0) >= max_per_document:
                    continue
                counts[document_id] = counts.get(document_id, 0) + 1
            output.append(chunk)
        return output

    def _procedure_title_candidates(
        self,
        query: str,
        locality_code: str,
        limit: int = 30,
    ) -> List[RetrievedChunk]:
        """Add long-tail procedure titles that fall outside top vector/BM25.

        There are 1,506 procedures and many share generic words such as
        "hỗ trợ". A title like "Hỗ trợ người cao tuổi ..." can rank outside the
        top 300 even though the user named it. Scan titles once per locality,
        keep the best title match per document, then let the title score rank
        the candidates.
        """
        cache = self._procedure_chunks_cache.get(locality_code)
        if cache is None:
            try:
                result = self.vector_store.collection.get(
                    where={
                        "$and": [
                            {"locality_code": str(locality_code)},
                            {"doc_type": "Thủ tục hành chính"},
                        ]
                    },
                    include=["documents", "metadatas"],
                )
            except Exception as exc:
                logger.warning(f"Procedure title lookup failed: {exc}")
                cache = []
            else:
                cache = [
                    RetrievedChunk(
                        text=text,
                        similarity_score=0.0,
                        metadata=metadata or {},
                    )
                    for text, metadata in zip(
                        result.get("documents") or [],
                        result.get("metadatas") or [],
                    )
                    if text and metadata
                ]
            self._procedure_chunks_cache[locality_code] = cache

        best_by_document: Dict[str, Tuple[float, RetrievedChunk]] = {}
        for chunk in cache:
            document_id = str(chunk.metadata.get("document_id") or "")
            if not document_id:
                continue
            score = procedure_title_score(query, chunk.metadata)
            if score <= 0.25:
                continue
            current = best_by_document.get(document_id)
            if current is None or score > current[0]:
                best_by_document[document_id] = (score, chunk)

        ranked = sorted(
            best_by_document.values(),
            key=lambda item: item[0],
            reverse=True,
        )
        return [
            RetrievedChunk(
                text=chunk.text,
                similarity_score=0.0,
                metadata=dict(chunk.metadata),
            )
            for _, chunk in ranked[:limit]
        ]

    def _procedure_fact_candidates(
        self,
        query: str,
        locality_code: str,
        title_candidates: List[RetrievedChunk],
        limit_documents: int = 1,
    ) -> List[RetrievedChunk]:
        """Attach the chunk that contains the requested fact (fee/time/records).

        Title matching returns the procedure header chunk, but "lệ phí" and
        "thời gian giải quyết" often live in a later chunk. Add those fact
        chunks for the best title matches so the LLM does not answer
        "không đủ thông tin" for a simple fee/time question.
        """
        text = normalize_for_match(query)
        markers: List[str] = []
        if "le phi" in text:
            markers.append("lệ phí")
        if "thoi gian" in text or "bao lau" in text:
            markers.append("thời gian giải quyết")
        if "ho so" in text or "giay to" in text:
            markers.append("hồ sơ")
        if not markers:
            return []

        document_ids = {
            str(chunk.metadata.get("document_id") or "")
            for chunk in title_candidates[:limit_documents]
        }
        cache = self._procedure_chunks_cache.get(locality_code) or []
        output: List[RetrievedChunk] = []
        for chunk in cache:
            document_id = str(chunk.metadata.get("document_id") or "")
            if document_id not in document_ids:
                continue
            lowered = (chunk.text or "").lower()
            if any(marker in lowered for marker in markers):
                output.append(
                    RetrievedChunk(
                        text=chunk.text,
                        similarity_score=0.6,
                        metadata=dict(chunk.metadata),
                    )
                )
        return output

    def _exact_doc_candidates(
        self,
        locality_code: Optional[str],
        constraints: QueryConstraints,
    ) -> List[RetrievedChunk]:
        """Fetch exact document-number chunks even if outside top candidates."""
        try:
            result = self.vector_store.collection.get(
                where={"locality_code": str(locality_code)} if locality_code else None,
                include=["documents", "metadatas"],
            )
        except Exception as exc:
            logger.warning(f"Exact doc lookup failed: {exc}")
            return []

        from app.rag.retrieval.query_constraints import doc_number_matches

        candidates = []
        for text, metadata in zip(
            result.get("documents") or [],
            result.get("metadatas") or [],
        ):
            if not text or not metadata:
                continue
            if doc_number_matches(metadata, constraints):
                candidates.append(
                    RetrievedChunk(
                        text=text,
                        similarity_score=1.0,
                        metadata=metadata,
                    )
                )
        return candidates
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[RetrievedChunk],
        bm25_results: List[Tuple],
        k: int
    ) -> List[RetrievedChunk]:
        """
        Combine results using Reciprocal Rank Fusion.
        
        RRF formula:
        RRF_score(d) = α × 1/(K + rank_vector(d)) + (1-α) × 1/(K + rank_bm25(d))
        
        Where:
        - K = 60 (constant from RRF paper)
        - rank(d) = position of document d in ranking (0-indexed)
        - α = weight for vector search
        
        Args:
            vector_results: Results from vector search (already sorted)
            bm25_results: Results from BM25 as (chunk, score) tuples
            k: Number of results to return
            
        Returns:
            Fused results sorted by RRF score
        """
        # Dictionary to accumulate scores
        # Key: chunk text (as unique identifier)
        # Value: {chunk, vector_score, bm25_score, total}
        scores = {}
        
        # Add vector search contribution
        for rank, chunk in enumerate(vector_results):
            chunk_key = chunk.text  # Use text as key
            vector_contribution = self.alpha / (self.RRF_K + rank)
            
            scores[chunk_key] = {
                'chunk': chunk,
                'vector_score': vector_contribution,
                'bm25_score': 0,
                'total': 0
            }
        
        # Add BM25 contribution
        for rank, (chunk, bm25_score) in enumerate(bm25_results):
            chunk_key = chunk.text
            bm25_contribution = (1 - self.alpha) / (self.RRF_K + rank)
            
            if chunk_key in scores:
                scores[chunk_key]['bm25_score'] = bm25_contribution
            else:
                scores[chunk_key] = {
                    'chunk': chunk,
                    'vector_score': 0,
                    'bm25_score': bm25_contribution,
                    'total': 0
                }
        
        # Calculate total RRF scores
        for chunk_key in scores:
            scores[chunk_key]['total'] = (
                scores[chunk_key]['vector_score'] + 
                scores[chunk_key]['bm25_score']
            )
        
        # Sort by total RRF score (descending)
        sorted_items = sorted(
            scores.values(),
            key=lambda x: x['total'],
            reverse=True
        )
        
        # Update chunks with RRF scores
        results = []
        for item in sorted_items[:k]:
            chunk = item['chunk']
            # Store RRF score as similarity_score
            chunk.similarity_score = item['total']
            # Store component scores in metadata
            chunk.metadata['rrf_vector_score'] = item['vector_score']
            chunk.metadata['rrf_bm25_score'] = item['bm25_score']
            results.append(chunk)
        
        return results
    
    def _filter_by_threshold(
        self, 
        chunks: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """
        Filter chunks by minimum similarity threshold.
        
        Removes low-quality results that could introduce noise
        or hallucination in generation.
        
        Args:
            chunks: Retrieved chunks
            
        Returns:
            Filtered chunks above threshold
        """
        filtered = [
            chunk for chunk in chunks
            if chunk.similarity_score >= self.min_similarity
        ]
        
        if not filtered:
            logger.warning(
                f"No results above threshold {self.min_similarity}",
                extra={"original_count": len(chunks)}
            )
        
        return filtered
    
    def get_stats(self) -> dict:
        """Get retriever statistics."""
        return {
            "type": "hybrid",
            "alpha": self.alpha,
            "min_similarity": self.min_similarity,
            "rrf_k": self.RRF_K,
            "reranking_enabled": self.use_reranking,
            "bm25s_stats": self.bm25_index.get_stats()
        }
