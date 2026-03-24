"""
VERITY — Financial Data Client
Pulls live fundamentals from yfinance (free) with FMP as backup.
Builds peer comparison tables.
All data cached in Redis to respect free-tier rate limits.
FMP: 250 calls/day free. yfinance: unlimited but unofficial.
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx
import structlog
import yfinance as yf
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.models.schemas import CompanyFundamentals, PeerComparisonTable
from app.services.cache import cache_get, cache_set

logger = structlog.get_logger(__name__)
settings = get_settings()

# Cache TTL: 4 hours for fundamentals (changes slowly intraday)
_FUNDAMENTALS_TTL = 60 * 60 * 4

# Peer map: expand over time
PEER_MAP: dict[str, list[str]] = {
    "AAPL": ["MSFT", "GOOGL", "META", "AMZN"],
    "NVDA": ["AMD", "INTC", "QCOM", "AVGO"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL"],
    "GOOGL": ["META", "MSFT", "AMZN", "SNAP"],
    "TSLA": ["GM", "F", "RIVN", "NIO"],
    "META": ["GOOGL", "SNAP", "PINS", "TWTR"],
    "AMZN": ["MSFT", "GOOGL", "WMT", "SHOP"],
    "JPM":  ["BAC", "WFC", "GS", "MS"],
    "GS":   ["MS", "JPM", "BAC", "C"],
}


async def get_fundamentals(ticker: str) -> CompanyFundamentals:
    """
    Fetch company fundamentals. Tries yfinance first, falls back to FMP.
    Results cached in Redis for 4 hours.
    """
    cache_key = f"fundamentals:{ticker.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        logger.info("fundamentals_cache_hit", ticker=ticker)
        return CompanyFundamentals(**cached)

    log = logger.bind(ticker=ticker)
    log.info("fundamentals_fetching")

    # Try yfinance first (free, no rate limit concerns)
    try:
        fundamentals = await _fetch_yfinance(ticker)
        await cache_set(cache_key, fundamentals.model_dump(mode="json"), ttl_seconds=_FUNDAMENTALS_TTL)
        return fundamentals
    except Exception as e:
        log.warning("yfinance_failed", error=str(e), fallback="fmp")

    # Fallback to FMP
    try:
        fundamentals = await _fetch_fmp(ticker)
        await cache_set(cache_key, fundamentals.model_dump(mode="json"), ttl_seconds=_FUNDAMENTALS_TTL)
        return fundamentals
    except Exception as e:
        log.error("fmp_failed", error=str(e))
        # Return minimal fundamentals rather than crashing the pipeline
        return CompanyFundamentals(ticker=ticker.upper(), company_name=ticker.upper(), data_source="failed")


async def _fetch_yfinance(ticker: str) -> CompanyFundamentals:
    """Fetch fundamentals from yfinance (sync library, run in thread pool)."""

    def _sync_fetch() -> dict:
        t = yf.Ticker(ticker)
        info = t.info
        return info

    # yfinance is sync — run in thread pool to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _sync_fetch)

    if not info or "symbol" not in info:
        raise ValueError(f"yfinance returned no data for {ticker}")

    def _safe(key: str, divisor: float = 1.0) -> float | None:
        val = info.get(key)
        if val is None or val == "N/A":
            return None
        try:
            return float(val) / divisor
        except (TypeError, ValueError):
            return None

    return CompanyFundamentals(
        ticker=ticker.upper(),
        company_name=info.get("longName") or info.get("shortName") or ticker.upper(),
        sector=info.get("sector"),
        industry=info.get("industry"),
        market_cap=_safe("marketCap"),
        enterprise_value=_safe("enterpriseValue"),
        revenue_ttm=_safe("totalRevenue"),
        revenue_growth_yoy=_safe("revenueGrowth"),
        gross_margin=_safe("grossMargins"),
        operating_margin=_safe("operatingMargins"),
        net_margin=_safe("profitMargins"),
        pe_ratio=_safe("trailingPE"),
        ev_ebitda=_safe("enterpriseToEbitda"),
        price_to_book=_safe("priceToBook"),
        price_to_sales=_safe("priceToSalesTrailing12Months"),
        debt_to_equity=_safe("debtToEquity"),
        current_ratio=_safe("currentRatio"),
        return_on_equity=_safe("returnOnEquity"),
        return_on_assets=_safe("returnOnAssets"),
        free_cash_flow_yield=_safe("freeCashflow"),
        data_source="yfinance",
    )


@retry(
    retry=retry_if_exception_type(httpx.HTTPStatusError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def _fetch_fmp(ticker: str) -> CompanyFundamentals:
    """Fetch fundamentals from Financial Modeling Prep API (backup)."""
    url = f"{settings.fmp_base_url}/profile/{ticker.upper()}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params={"apikey": settings.fmp_api_key})
        resp.raise_for_status()
        data = resp.json()

    if not data or not isinstance(data, list) or len(data) == 0:
        raise ValueError(f"FMP returned no data for {ticker}")

    profile = data[0]

    def _safe(key: str) -> float | None:
        val = profile.get(key)
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    return CompanyFundamentals(
        ticker=ticker.upper(),
        company_name=profile.get("companyName", ticker.upper()),
        sector=profile.get("sector"),
        industry=profile.get("industry"),
        market_cap=_safe("mktCap"),
        pe_ratio=_safe("pe"),
        price_to_book=_safe("priceToBook"),
        gross_margin=_safe("grossProfitTTM"),
        data_source="fmp",
    )


async def get_peer_comparison(ticker: str) -> PeerComparisonTable:
    """
    Build a peer comparison table for a ticker.
    Fetches fundamentals for each peer in parallel.
    """
    ticker = ticker.upper()
    peers = PEER_MAP.get(ticker, [])

    if not peers:
        # Generic fallback: use S&P 500 ETF as single benchmark
        peers = ["SPY"]

    log = logger.bind(ticker=ticker, peers=peers)
    log.info("peer_comparison_building")

    # Fetch all peer fundamentals concurrently
    tasks = [get_fundamentals(p) for p in peers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_peers: list[CompanyFundamentals] = []
    for peer, result in zip(peers, results):
        if isinstance(result, Exception):
            log.warning("peer_fetch_failed", peer=peer, error=str(result))
        else:
            valid_peers.append(result)

    log.info("peer_comparison_complete", peers_fetched=len(valid_peers))
    return PeerComparisonTable(subject_ticker=ticker, peers=valid_peers)


async def get_price_history(ticker: str, period: str = "1y") -> list[dict]:
    """
    Fetch historical price data for charting.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    """
    cache_key = f"price_history:{ticker.upper()}:{period}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    def _sync_fetch() -> list[dict]:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty:
            return []
        hist.index = hist.index.strftime("%Y-%m-%d")
        return [
            {"date": date, "close": round(row["Close"], 2), "volume": int(row["Volume"])}
            for date, row in hist.iterrows()
        ]

    loop = asyncio.get_event_loop()
    history = await loop.run_in_executor(None, _sync_fetch)

    await cache_set(cache_key, history, ttl_seconds=3600)
    return history
