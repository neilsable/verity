"""
VERITY — Document Chunking Pipeline
Semantic chunking with overlap for SEC filings and transcripts.
Uses tiktoken for accurate token counting (same tokenizer as OpenAI embeddings).
Preserves document structure — never splits mid-sentence.
"""

import hashlib
import re
import uuid
from datetime import datetime

import structlog
import tiktoken

from app.core.config import get_settings
from app.models.schemas import DocumentChunk

logger = structlog.get_logger(__name__)
settings = get_settings()

# Use cl100k_base — same tokenizer as text-embedding-3-small
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in a string using the embedding model's tokenizer."""
    return len(_TOKENIZER.encode(text))


def _split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences while preserving financial notation.
    Handles abbreviations like 'vs.', 'approx.', 'FY2024.', SEC filing patterns.
    """
    # Protect common abbreviations from splitting
    protected = text
    abbrevs = [
        "vs.", "approx.", "est.", "inc.", "corp.", "ltd.", "co.",
        "fig.", "no.", "sec.", "dept.", "yr.", "mo.", "q1.", "q2.", "q3.", "q4.",
        "u.s.", "u.k.", "e.g.", "i.e.", "et al.", "pp.", "p.",
    ]
    placeholders: dict[str, str] = {}
    for i, abbrev in enumerate(abbrevs):
        placeholder = f"ABBREV{i}PLACEHOLDER"
        placeholders[placeholder] = abbrev
        protected = protected.replace(abbrev, placeholder)
        protected = protected.replace(abbrev.upper(), placeholder)

    # Split on sentence endings followed by whitespace + capital
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'\(])", protected)

    # Restore abbreviations
    result = []
    for sentence in sentences:
        for placeholder, abbrev in placeholders.items():
            sentence = sentence.replace(placeholder, abbrev)
        sentence = sentence.strip()
        if sentence:
            result.append(sentence)

    return result if result else [text]


def chunk_document(
    text: str,
    document_id: str,
    ticker: str,
    source_type: str,
    source_url: str,
    filing_date: datetime,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[DocumentChunk]:
    """
    Split a document into overlapping semantic chunks.

    Strategy:
    1. Split into sentences (sentence-aware splitter)
    2. Greedily pack sentences into chunks up to chunk_size tokens
    3. Add overlap by including the last N tokens from the previous chunk
    4. Never cut mid-sentence

    Returns a list of DocumentChunk objects ready for embedding.
    """
    chunk_size = chunk_size or settings.chunk_size
    overlap = chunk_overlap or settings.chunk_overlap

    log = logger.bind(ticker=ticker, source_type=source_type, document_id=document_id)

    if not text or not text.strip():
        log.warning("chunker_empty_document")
        return []

    # Clean text: normalize whitespace, remove null bytes
    text = text.replace("\x00", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {3,}", " ", text)

    sentences = _split_into_sentences(text)

    chunks: list[DocumentChunk] = []
    current_sentences: list[str] = []
    current_tokens = 0
    overlap_buffer: str = ""  # Trailing text from previous chunk for overlap

    def _make_chunk(sentences: list[str], index: int, prefix: str = "") -> DocumentChunk:
        content = (prefix + " " + " ".join(sentences)).strip()
        token_count = count_tokens(content)

        # Stable chunk ID based on content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        chunk_id = f"{document_id}_{index}_{content_hash}"

        return DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            ticker=ticker,
            source_type=source_type,
            source_url=source_url,
            filing_date=filing_date,
            chunk_index=index,
            text=content,
            token_count=token_count,
        )

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)

        # If a single sentence exceeds chunk_size, split it by words
        if sentence_tokens > chunk_size:
            words = sentence.split()
            sub_sentences = []
            sub = []
            sub_tok = 0
            for word in words:
                wt = count_tokens(word)
                if sub_tok + wt > chunk_size and sub:
                    sub_sentences.append(" ".join(sub))
                    sub = [word]
                    sub_tok = wt
                else:
                    sub.append(word)
                    sub_tok += wt
            if sub:
                sub_sentences.append(" ".join(sub))
            for ss in sub_sentences:
                sentences.insert(sentences.index(sentence) + 1, ss)
            continue

        if current_tokens + sentence_tokens > chunk_size and current_sentences:
            # Emit current chunk
            chunk = _make_chunk(current_sentences, len(chunks), overlap_buffer)
            chunks.append(chunk)

            # Build overlap buffer from tail of current chunk
            overlap_sentences: list[str] = []
            overlap_tok = 0
            for s in reversed(current_sentences):
                st = count_tokens(s)
                if overlap_tok + st > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tok += st
            overlap_buffer = " ".join(overlap_sentences)

            current_sentences = [sentence]
            current_tokens = sentence_tokens
        else:
            current_sentences.append(sentence)
            current_tokens += sentence_tokens

    # Emit final chunk
    if current_sentences:
        chunk = _make_chunk(current_sentences, len(chunks), overlap_buffer)
        chunks.append(chunk)

    log.info(
        "document_chunked",
        chunks=len(chunks),
        total_tokens=sum(c.token_count for c in chunks),
        avg_tokens=sum(c.token_count for c in chunks) // max(len(chunks), 1),
    )
    return chunks


def chunk_multiple_documents(
    documents: list[dict],
) -> list[DocumentChunk]:
    """
    Chunk a list of documents in batch.
    Each dict must have: text, document_id, ticker, source_type, source_url, filing_date.
    """
    all_chunks: list[DocumentChunk] = []
    for doc in documents:
        chunks = chunk_document(**doc)
        all_chunks.extend(chunks)

    logger.info("batch_chunking_complete", documents=len(documents), total_chunks=len(all_chunks))
    return all_chunks
