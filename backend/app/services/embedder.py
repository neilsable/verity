"""
VERITY — Embedding Pipeline
Batch embedding with OpenAI text-embedding-3-small.
Tracks token usage and cost per job.
Handles rate limits with exponential backoff.
"""

import asyncio
from typing import Any

import structlog
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.models.schemas import DocumentChunk, EmbeddedChunk

logger = structlog.get_logger(__name__)
settings = get_settings()

_openai_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=60.0,
            max_retries=0,  # We handle retries ourselves via tenacity
        )
    return _openai_client


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(settings.llm_max_retries),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)
async def _embed_batch(texts: list[str]) -> tuple[list[list[float]], int]:
    """
    Embed a batch of texts. Returns (embeddings, total_tokens).
    Retries on rate limit or transient errors.
    """
    client = get_openai_client()
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )
    embeddings = [item.embedding for item in response.data]
    total_tokens = response.usage.total_tokens
    return embeddings, total_tokens


async def embed_chunks(
    chunks: list[DocumentChunk],
    job_id: str | None = None,
) -> tuple[list[EmbeddedChunk], dict[str, Any]]:
    """
    Embed a list of DocumentChunks in batches.
    Returns (embedded_chunks, cost_metadata).

    Batching strategy:
    - Group chunks into batches of EMBEDDING_BATCH_SIZE
    - Run batches with a small delay to respect rate limits
    - Track total tokens and cost
    """
    if not chunks:
        return [], {"total_tokens": 0, "cost_usd": 0.0, "chunks": 0}

    log = logger.bind(job_id=job_id, total_chunks=len(chunks))
    log.info("embedding_started")

    batch_size = settings.embedding_batch_size
    embedded: list[EmbeddedChunk] = []
    total_tokens = 0
    failed_chunks: list[str] = []

    # Process in batches
    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        texts = [chunk.text for chunk in batch]

        try:
            embeddings, batch_tokens = await _embed_batch(texts)
            total_tokens += batch_tokens

            for chunk, embedding in zip(batch, embeddings):
                pinecone_id = f"{chunk.ticker}_{chunk.chunk_id}"
                embedded.append(
                    EmbeddedChunk(
                        **chunk.model_dump(),
                        embedding=embedding,
                        pinecone_id=pinecone_id,
                    )
                )

            log.info(
                "embedding_batch_complete",
                batch_start=batch_start,
                batch_size=len(batch),
                tokens=batch_tokens,
            )

        except Exception as e:
            log.error(
                "embedding_batch_failed",
                batch_start=batch_start,
                error=str(e),
            )
            failed_chunks.extend([c.chunk_id for c in batch])
            # Continue with remaining batches — partial results are better than none
            continue

        # Small delay between batches to avoid rate limits
        if batch_start + batch_size < len(chunks):
            await asyncio.sleep(0.5)

    cost_usd = settings.embedding_cost_usd(total_tokens)

    metadata = {
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "chunks_embedded": len(embedded),
        "chunks_failed": len(failed_chunks),
        "failed_chunk_ids": failed_chunks,
        "model": settings.embedding_model,
    }

    log.info(
        "embedding_complete",
        embedded=len(embedded),
        failed=len(failed_chunks),
        total_tokens=total_tokens,
        cost_usd=round(cost_usd, 6),
    )

    return embedded, metadata


async def embed_query(query: str) -> list[float]:
    """
    Embed a single query string for similarity search.
    Used at retrieval time (not stored in Pinecone).
    """
    embeddings, _ = await _embed_batch([query])
    return embeddings[0]
