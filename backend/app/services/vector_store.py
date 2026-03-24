"""
VERITY — Pinecone Vector Store Client
Upsert, query, and namespace management for embedded document chunks.
Namespaces isolate data per ticker (e.g. "AAPL", "NVDA").
"""

from typing import Any

import structlog
from pinecone import Pinecone, ServerlessSpec
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.models.schemas import DocumentChunk, EmbeddedChunk
from app.services.embedder import embed_query

logger = structlog.get_logger(__name__)
settings = get_settings()

_pinecone_client: Pinecone | None = None
_index = None


def get_pinecone_index():
    """Get or initialise the Pinecone index. Lazy singleton."""
    global _pinecone_client, _index

    if _index is not None:
        return _index

    _pinecone_client = Pinecone(api_key=settings.pinecone_api_key)

    existing = [idx.name for idx in _pinecone_client.list_indexes()]

    if settings.pinecone_index_name not in existing:
        logger.info("pinecone_creating_index", index=settings.pinecone_index_name)
        _pinecone_client.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.embedding_dimensions,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    _index = _pinecone_client.Index(settings.pinecone_index_name)
    logger.info("pinecone_index_ready", index=settings.pinecone_index_name)
    return _index


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
)
async def upsert_chunks(
    chunks: list[EmbeddedChunk],
    namespace: str | None = None,
) -> dict[str, Any]:
    """
    Upsert embedded chunks into Pinecone.
    Namespace defaults to the ticker symbol (e.g. "AAPL").
    Batches upserts in groups of 100 (Pinecone free tier limit).
    """
    if not chunks:
        return {"upserted": 0}

    index = get_pinecone_index()
    ns = namespace or chunks[0].ticker.upper()
    log = logger.bind(namespace=ns, chunks=len(chunks))

    upsert_batch_size = 100
    total_upserted = 0

    for batch_start in range(0, len(chunks), upsert_batch_size):
        batch = chunks[batch_start : batch_start + upsert_batch_size]

        vectors = []
        for chunk in batch:
            metadata = {
                "ticker": chunk.ticker,
                "source_type": chunk.source_type,
                "source_url": chunk.source_url,
                "filing_date": chunk.filing_date.isoformat(),
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
                "text": chunk.text[:1000],  # Pinecone metadata limit: store truncated text
                "document_id": chunk.document_id,
            }
            if chunk.page_number is not None:
                metadata["page_number"] = chunk.page_number

            vectors.append({
                "id": chunk.pinecone_id,
                "values": chunk.embedding,
                "metadata": metadata,
            })

        result = index.upsert(vectors=vectors, namespace=ns)
        total_upserted += result.get("upserted_count", len(batch))

    log.info("pinecone_upsert_complete", upserted=total_upserted)
    return {"upserted": total_upserted, "namespace": ns}


async def query_similar(
    query: str,
    ticker: str,
    top_k: int = 8,
    filter_source_type: str | None = None,
    min_score: float = 0.70,
) -> list[DocumentChunk]:
    """
    Semantic search: embed the query and find the most similar chunks.
    Filters by ticker namespace and optionally by source type.
    Returns DocumentChunks sorted by relevance (best first).
    """
    log = logger.bind(ticker=ticker, query=query[:60])

    query_embedding = await embed_query(query)
    index = get_pinecone_index()
    ns = ticker.upper()

    filter_dict: dict | None = None
    if filter_source_type:
        filter_dict = {"source_type": {"$eq": filter_source_type}}

    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        namespace=ns,
        include_metadata=True,
        filter=filter_dict,
    )

    matches = results.get("matches", [])
    chunks: list[DocumentChunk] = []

    for match in matches:
        score = match.get("score", 0.0)
        if score < min_score:
            continue

        meta = match.get("metadata", {})
        try:
            from datetime import datetime
            chunk = DocumentChunk(
                chunk_id=match["id"],
                document_id=meta.get("document_id", ""),
                ticker=meta.get("ticker", ticker),
                source_type=meta.get("source_type", ""),
                source_url=meta.get("source_url", ""),
                filing_date=datetime.fromisoformat(meta.get("filing_date", "2020-01-01")),
                chunk_index=meta.get("chunk_index", 0),
                text=meta.get("text", ""),
                token_count=meta.get("token_count", 0),
                page_number=meta.get("page_number"),
            )
            chunks.append(chunk)
        except Exception as e:
            log.warning("pinecone_chunk_parse_error", error=str(e), match_id=match["id"])
            continue

    log.info("pinecone_query_complete", results=len(chunks), top_score=matches[0]["score"] if matches else 0)
    return chunks


async def delete_namespace(ticker: str) -> None:
    """Delete all vectors for a ticker namespace (used for re-indexing)."""
    index = get_pinecone_index()
    ns = ticker.upper()
    index.delete(delete_all=True, namespace=ns)
    logger.info("pinecone_namespace_deleted", namespace=ns)


async def get_index_stats() -> dict:
    """Return index statistics for monitoring."""
    index = get_pinecone_index()
    return index.describe_index_stats()
