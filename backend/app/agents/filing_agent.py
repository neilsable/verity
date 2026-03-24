"""
VERITY — Filing Agent
1. Fetches recent SEC filings (10-K, 10-Q, 8-K) from EDGAR
2. Downloads and chunks the filing text
3. Embeds chunks and upserts to Pinecone
4. Retrieves the most relevant passages for the research brief
"""

import structlog

from app.agents.base import BaseAgent
from app.models.schemas import AgentName, ResearchState
from app.services.chunker import chunk_document
from app.services.embedder import embed_chunks
from app.services.sec_edgar import fetch_filing_text, get_recent_filings
from app.services.vector_store import query_similar, upsert_chunks

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are a financial analyst specialising in SEC filings analysis.
You have been given relevant excerpts from SEC filings (10-K, 10-Q, 8-K).
Your job is to extract the most important financial facts, risks, and disclosures
that are relevant to the research question.

Be precise and factual. Only state what is directly supported by the provided text.
Always note the filing type and approximate date for each fact you cite.
Never invent or infer figures that are not present in the text."""


class FilingAgent(BaseAgent):
    name = AgentName.FILING

    async def run(self, state: ResearchState) -> ResearchState:
        ticker = state.ticker
        log = self.log.bind(ticker=ticker)

        # Step 1: Fetch filing metadata from EDGAR
        log.info("filing_agent_fetching_filings")
        try:
            filings = await get_recent_filings(ticker, max_per_type=2)
        except Exception as e:
            log.warning("filing_fetch_failed", error=str(e))
            filings = []

        if not filings:
            log.warning("no_filings_found", ticker=ticker)
            return state.model_copy(update={
                "agent_outputs": {
                    **state.agent_outputs,
                    "filing": {"summary": "No SEC filings found.", "chunks_indexed": 0},
                }
            })

        # Step 2: Download text + chunk + embed the most recent 10-K and latest 10-Q
        priority_filings = [f for f in filings if str(f.filing_type) in ("10-K", "10-Q")][:3]
        all_chunks = []

        for filing in priority_filings:
            try:
                text = await fetch_filing_text(filing.document_url)
                if len(text) < 500:
                    continue

                chunks = chunk_document(
                    text=text[:150_000],  # Cap at 150k chars to control cost
                    document_id=filing.accession_number,
                    ticker=ticker,
                    source_type=filing.filing_type.value,
                    source_url=filing.document_url,
                    filing_date=filing.filing_date,
                )
                all_chunks.extend(chunks)
                log.info("filing_chunked", filing_type=filing.filing_type, chunks=len(chunks))

            except Exception as e:
                log.warning("filing_download_failed", url=filing.document_url, error=str(e))
                continue

        # Step 3: Embed and upsert to Pinecone
        chunks_indexed = 0
        if all_chunks:
            try:
                embedded, embed_meta = await embed_chunks(all_chunks, job_id=str(state.job_id))
                if embedded:
                    await upsert_chunks(embedded, namespace=ticker)
                    chunks_indexed = embed_meta["chunks_embedded"]

                    # Update cost tracking
                    embed_cost = embed_meta["cost_usd"]
                    state = state.model_copy(update={
                        "total_cost_usd": round(state.total_cost_usd + embed_cost, 6)
                    })
                    log.info("filing_indexed", chunks=chunks_indexed, cost_usd=embed_cost)
            except Exception as e:
                log.warning("filing_embed_failed", error=str(e))

        # Step 4: RAG — retrieve relevant chunks for the research brief
        research_query = state.research_brief or f"Key financial metrics and risks for {ticker}"
        try:
            relevant_chunks = await query_similar(
                query=research_query,
                ticker=ticker,
                top_k=10,
            )
        except Exception as e:
            log.warning("filing_rag_failed", error=str(e))
            relevant_chunks = []

        # Step 5: Synthesise retrieved chunks into a structured summary via LLM
        if relevant_chunks:
            context = "\n\n---\n\n".join([
                f"[{c.source_type} | {c.filing_date.strftime('%Y-%m-%d')}]\n{c.text}"
                for c in relevant_chunks[:8]
            ])

            prompt = f"""Company: {state.company_name or ticker} ({ticker})
Research question: {state.research_brief}

SEC Filing Excerpts:
{context}

Extract the key financial facts, risks, and disclosures relevant to the research question."""

            summary = await self.llm(prompt, SYSTEM_PROMPT, state, max_tokens=1500)
        else:
            summary = f"No relevant filing passages retrieved for {ticker}."

        return state.model_copy(update={
            "sec_filings": filings,
            "relevant_chunks": relevant_chunks,
            "agent_outputs": {
                **state.agent_outputs,
                "filing": {
                    "summary": summary,
                    "chunks_indexed": chunks_indexed,
                    "filings_processed": len(priority_filings),
                    "relevant_chunks": len(relevant_chunks),
                },
            },
        })


filing_agent = FilingAgent()


async def filing_node(state: ResearchState) -> ResearchState:
    return await filing_agent(state)
