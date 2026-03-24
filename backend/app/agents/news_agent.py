"""
VERITY — News Agent
Fetches recent news, applies temporal decay, scores sentiment,
and identifies material events relevant to the research brief.
"""

import structlog

from app.agents.base import BaseAgent
from app.models.schemas import AgentName, ResearchState
from app.services.news_client import get_news

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are a financial analyst specialising in news and sentiment analysis.
You have been given recent news articles about a company, scored for sentiment and materiality.
Provide a structured news analysis covering:
- Key recent developments and their likely impact
- Overall news sentiment trend
- Any material events (earnings, M&A, regulatory, management changes)
- Risks or catalysts surfaced by recent news
Be concise and direct. Note the recency and source of key items."""


class NewsAgent(BaseAgent):
    name = AgentName.NEWS

    async def run(self, state: ResearchState) -> ResearchState:
        ticker = state.ticker
        company_name = state.company_name or ticker

        articles = await get_news(ticker, company_name=company_name, days_back=14)

        if not articles:
            return state.model_copy(update={
                "news_articles": [],
                "agent_outputs": {
                    **state.agent_outputs,
                    "news": {"summary": "No recent news found.", "articles": 0},
                },
            })

        # Format top articles for LLM
        top_articles = articles[:12]
        news_text = "\n\n".join([
            f"[{a.published_at.strftime('%Y-%m-%d')} | {a.source_name} | "
            f"Sentiment: {a.sentiment_score:+.2f} | Weight: {a.temporal_weight:.2f}"
            f"{' | MATERIAL' if a.is_material else ''}]\n"
            f"TITLE: {a.title}\n"
            f"{'DESC: ' + a.description if a.description else ''}"
            for a in top_articles
        ])

        avg_sentiment = sum(a.sentiment_score for a in top_articles) / len(top_articles)
        material_count = sum(1 for a in top_articles if a.is_material)

        prompt = f"""Company: {company_name} ({ticker})
Research focus: {state.research_brief}
Articles analysed: {len(top_articles)} (past 14 days)
Average sentiment: {avg_sentiment:+.3f}
Material events: {material_count}

Recent news articles:
{news_text}

Provide a structured news and sentiment analysis."""

        analysis = await self.llm(prompt, SYSTEM_PROMPT, state, max_tokens=1000)

        return state.model_copy(update={
            "news_articles": articles,
            "agent_outputs": {
                **state.agent_outputs,
                "news": {
                    "summary": analysis,
                    "articles": len(articles),
                    "material_events": material_count,
                    "avg_sentiment": round(avg_sentiment, 3),
                },
            },
        })


news_agent = NewsAgent()


async def news_node(state: ResearchState) -> ResearchState:
    return await news_agent(state)
