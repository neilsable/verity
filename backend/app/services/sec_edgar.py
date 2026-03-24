"""
VERITY — SEC EDGAR Async Client
Fetches 10-K, 10-Q, 8-K filings from SEC EDGAR free API.
Rate limit: 10 req/sec per SEC fair-use policy.
No API key required — just a descriptive User-Agent.
"""

import asyncio
import re
from datetime import datetime
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.models.schemas import FilingType, SECFiling

logger = structlog.get_logger(__name__)
settings = get_settings()

# SEC rate limit: max 10 requests/second
_SEC_SEMAPHORE = asyncio.Semaphore(8)
_SEC_RATE_LIMITER = asyncio.Semaphore(8)


def _get_headers() -> dict[str, str]:
    return {
        "User-Agent": settings.sec_edgar_user_agent,
        "Accept": "application/json",
    }


@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def _get(client: httpx.AsyncClient, url: str, **kwargs: Any) -> dict:
    """Rate-limited GET with retry logic."""
    async with _SEC_SEMAPHORE:
        resp = await client.get(url, headers=_get_headers(), timeout=30.0, **kwargs)
        resp.raise_for_status()
        await asyncio.sleep(0.12)  # Stay under 10 req/sec
        return resp.json()


async def get_cik_for_ticker(ticker: str) -> str:
    """
    Resolve a stock ticker to its SEC CIK number.
    Uses the SEC company tickers JSON endpoint.
    """
    log = logger.bind(ticker=ticker)
    url = "https://www.sec.gov/files/company_tickers.json"

    async with httpx.AsyncClient() as client:
        data = await _get(client, url)

    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            cik = str(entry["cik_str"]).zfill(10)
            log.info("sec_cik_resolved", cik=cik)
            return cik

    raise ValueError(f"Could not resolve CIK for ticker: {ticker}")


async def get_recent_filings(
    ticker: str,
    filing_types: list[FilingType] | None = None,
    max_per_type: int = 3,
) -> list[SECFiling]:
    """
    Fetch recent SEC filings for a ticker.
    Returns up to max_per_type filings per filing type.
    """
    log = logger.bind(ticker=ticker)

    if filing_types is None:
        filing_types = [FilingType.ANNUAL_REPORT, FilingType.QUARTERLY_REPORT, FilingType.CURRENT_REPORT]

    cik = await get_cik_for_ticker(ticker)
    url = f"{settings.sec_edgar_submissions_url}/CIK{cik}.json"

    async with httpx.AsyncClient() as client:
        data = await _get(client, url)

    filings: list[SECFiling] = []
    recent = data.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    report_dates = recent.get("reportDate", [])

    counts: dict[str, int] = {}

    for i, form in enumerate(forms):
        if i >= len(dates):
            break

        matched_type = None
        for ft in filing_types:
            if form == ft.value:
                matched_type = ft
                break

        if matched_type is None:
            continue

        type_key = matched_type.value
        counts[type_key] = counts.get(type_key, 0)
        if counts[type_key] >= max_per_type:
            continue
        counts[type_key] += 1

        accession = accessions[i].replace("-", "")
        doc = primary_docs[i] if i < len(primary_docs) else ""
        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession}/{doc}"
        )
        full_text_url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{accession}%22"
            f"&dateRange=custom&startdt={dates[i]}&enddt={dates[i]}"
        )

        period = None
        if i < len(report_dates) and report_dates[i]:
            try:
                period = datetime.strptime(report_dates[i], "%Y-%m-%d")
            except ValueError:
                pass

        filings.append(SECFiling(
            ticker=ticker.upper(),
            cik=cik,
            filing_type=matched_type,
            filing_date=datetime.strptime(dates[i], "%Y-%m-%d"),
            period_of_report=period,
            accession_number=accessions[i],
            document_url=doc_url,
            full_text_url=full_text_url,
        ))

    log.info("sec_filings_fetched", count=len(filings), ticker=ticker)
    return filings


async def fetch_filing_text(document_url: str) -> str:
    """
    Download the full text of an SEC filing document.
    Strips HTML tags and returns clean text.
    """
    async with httpx.AsyncClient() as client:
        async with _SEC_SEMAPHORE:
            resp = await client.get(
                document_url,
                headers=_get_headers(),
                timeout=60.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            await asyncio.sleep(0.12)

    content = resp.text

    # Strip HTML if present
    if "<html" in content.lower() or "<HTML" in content:
        # Remove script/style blocks
        content = re.sub(r"<script[^>]*>.*?</script>", " ", content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<style[^>]*>.*?</style>", " ", content, flags=re.DOTALL | re.IGNORECASE)
        # Remove all tags
        content = re.sub(r"<[^>]+>", " ", content)
        # Collapse whitespace
        content = re.sub(r"\s+", " ", content).strip()

    logger.info("sec_filing_fetched", url=document_url, chars=len(content))
    return content


async def search_filings_fulltext(
    ticker: str,
    query: str,
    filing_type: str = "10-K",
    date_from: str = "2020-01-01",
) -> list[dict]:
    """
    Full-text search across SEC filings using EDGAR EFTS.
    Returns list of matching filing metadata.
    """
    params = {
        "q": f'"{ticker}" {query}',
        "dateRange": "custom",
        "startdt": date_from,
        "forms": filing_type,
    }

    url = "https://efts.sec.gov/LATEST/search-index"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params=params,
            headers=_get_headers(),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

    hits = data.get("hits", {}).get("hits", [])
    logger.info("sec_fulltext_search", ticker=ticker, query=query, hits=len(hits))
    return hits
