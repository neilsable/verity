"""
VERITY — News Client
NewsAPI ingestion with temporal decay weighting and basic sentiment scoring.
Free tier: 100 calls/day — aggressive caching is essential.
Temporal decay: recent news weighted higher, older news discounted exponentially.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.models.schemas import NewsArticle, SentimentScore
from app.services.cache import cache_get, cache_set

logger = structlog.get_logger(__name__)
settings = get_settings()

# Cache news for 2 hours — balances freshness vs. API quota
_NEWS_TTL = 60 * 60 * 2

# Temporal decay half-life: 3 days
# A 3-day-old article has weight 0.5 vs a fresh article (weight 1.0)
_DECAY_HALF_LIFE_DAYS = 3.0

# Simple sentiment word lists (production would use a proper NLP model)
_POSITIVE_WORDS = {
    "beats", "beat", "exceeds", "exceeded", "record", "growth", "surge", "soars",
    "strong", "robust", "upgrade", "raised", "outperform", "bullish", "positive",
    "profit", "revenue", "expansion", "breakthrough", "partnership", "win",
    "innovative", "leading", "gains", "rally", "rises", "boosts", "accelerates",
}
_NEGATIVE_WORDS = {
    "misses", "missed", "miss", "decline", "falls", "drops", "disappoints",
    "weak", "loss", "losses", "downgrade", "cut", "underperform", "bearish",
    "negative", "layoffs", "investigation", "lawsuit", "fine", "penalty",
    "recall", "breach", "hack", "fraud", "concern", "risk", "warn", "slowdown",
    "cuts", "struggles", "tumbles", "plunges", "crash",
}
_MATERIAL_KEYWORDS = {
    "acquisition", "merger", "ceo", "cfo", "earnings", "revenue", "guidance",
    "fda", "sec", "lawsuit", "settlement", "bankruptcy", "dividend", "buyback",
    "ipo", "offering", "breach", "investigation", "antitrust", "regulation",
    "patent", "contract", "partnership", "layoff", "restructuring",
}


def _compute_temporal_weight(published_at: datetime) -> float:
    """
    Exponential decay: weight = 0.5 ^ (age_days / half_life)
    - Today: 1.0
    - 3 days ago: 0.5
    - 6 days ago: 0.25
    - 12 days ago: 0.0625
    """
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    age_days = (now - published_at).total_seconds() / 86400
    age_days = max(0.0, age_days)
    weight = math.pow(0.5, age_days / _DECAY_HALF_LIFE_DAYS)
    return round(weight, 4)


def _score_sentiment(title: str, description: str | None) -> tuple[float, SentimentScore]:
    """
    Simple bag-of-words sentiment scorer.
    Returns (score, label) where score is in [-1.0, +1.0].
    Production upgrade: replace with a fine-tuned financial sentiment model.
    """
    text = (title + " " + (description or "")).lower()
    words = set(text.split())

    pos_hits = len(words & _POSITIVE_WORDS)
    neg_hits = len(words & _NEGATIVE_WORDS)
    total = pos_hits + neg_hits

    if total == 0:
        return 0.0, SentimentScore.NEUTRAL

    raw = (pos_hits - neg_hits) / total

    if raw > 0.6:
        return raw, SentimentScore.VERY_POSITIVE
    elif raw > 0.2:
        return raw, SentimentScore.POSITIVE
    elif raw < -0.6:
        return raw, SentimentScore.VERY_NEGATIVE
    elif raw < -0.2:
        return raw, SentimentScore.NEGATIVE
    else:
        return raw, SentimentScore.NEUTRAL


def _check_materiality(title: str, description: str | None) -> tuple[bool, str | None]:
    """Check if an article is likely a material event."""
    text = (title + " " + (description or "")).lower()
    words = set(text.split())
    hits = words & _MATERIAL_KEYWORDS

    if hits:
        return True, f"Contains material keywords: {', '.join(sorted(hits)[:3])}"
    return False, None


@retry(
    retry=retry_if_exception_type(httpx.HTTPStatusError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def _fetch_from_newsapi(ticker: str, company_name: str, days_back: int) -> list[dict]:
    """Raw fetch from NewsAPI."""
    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{settings.news_api_base_url}/everything",
            params={
                "q": f'"{ticker}" OR "{company_name}"',
                "from": from_date,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": 20,
                "apiKey": settings.news_api_key,
            },
        )
        resp.raise_for_status()
        return resp.json().get("articles", [])


async def get_news(
    ticker: str,
    company_name: str | None = None,
    days_back: int = 14,
) -> list[NewsArticle]:
    """
    Fetch, score, and weight news articles for a ticker.
    Returns articles sorted by temporal_weight × |sentiment_score| (most impactful first).
    """
    log = logger.bind(ticker=ticker)
    cache_key = f"news:{ticker.upper()}:{days_back}"

    cached = await cache_get(cache_key)
    if cached:
        log.info("news_cache_hit", ticker=ticker)
        return [NewsArticle(**a) for a in cached]

    company_name = company_name or ticker

    try:
        raw_articles = await _fetch_from_newsapi(ticker, company_name, days_back)
    except Exception as e:
        log.warning("newsapi_failed", error=str(e))
        return []

    articles: list[NewsArticle] = []

    for raw in raw_articles:
        if not raw.get("url") or raw.get("title") == "[Removed]":
            continue

        title = raw.get("title", "")
        description = raw.get("description")

        # Parse published date
        try:
            pub_str = raw.get("publishedAt", "")
            published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            published_at = datetime.now(timezone.utc)

        sentiment_score, _ = _score_sentiment(title, description)
        temporal_weight = _compute_temporal_weight(published_at)
        is_material, materiality_reason = _check_materiality(title, description)

        # Stable article ID from URL hash
        import hashlib
        article_id = hashlib.sha256(raw["url"].encode()).hexdigest()[:16]

        articles.append(NewsArticle(
            article_id=article_id,
            ticker=ticker.upper(),
            title=title,
            description=description,
            url=raw["url"],
            published_at=published_at,
            source_name=raw.get("source", {}).get("name", "Unknown"),
            sentiment_score=round(sentiment_score, 3),
            temporal_weight=temporal_weight,
            is_material=is_material,
            materiality_reason=materiality_reason,
        ))

    # Sort: most impactful first (high temporal weight × high |sentiment|)
    articles.sort(
        key=lambda a: a.temporal_weight * abs(a.sentiment_score),
        reverse=True,
    )

    # Cache the result
    await cache_set(
        cache_key,
        [a.model_dump(mode="json") for a in articles],
        ttl_seconds=_NEWS_TTL,
    )

    log.info(
        "news_fetched",
        articles=len(articles),
        material=sum(1 for a in articles if a.is_material),
        avg_sentiment=round(sum(a.sentiment_score for a in articles) / max(len(articles), 1), 3),
    )

    return articles
