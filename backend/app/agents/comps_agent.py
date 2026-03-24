"""
VERITY — Comps Agent
Fetches live fundamentals and builds a peer comparison table.
"""

import structlog

from app.agents.base import BaseAgent
from app.models.schemas import AgentName, ResearchState
from app.services.financials import get_fundamentals, get_peer_comparison

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are a financial analyst specialising in comparable company analysis.
You have been given financial metrics for a company and its peers.
Provide a concise, structured valuation analysis covering:
- How the subject company's valuation compares to peers (premium/discount)
- Key differentiating metrics (growth, margins, returns)
- Whether the current valuation appears justified based on fundamentals
Be direct and quantitative. Use specific numbers."""


class CompsAgent(BaseAgent):
    name = AgentName.COMPS

    async def run(self, state: ResearchState) -> ResearchState:
        ticker = state.ticker

        subject = await get_fundamentals(ticker)
        peer_table = await get_peer_comparison(ticker)

        def _fmt(v: float | None, pct: bool = False) -> str:
            if v is None:
                return "N/A"
            if pct:
                return f"{v*100:.1f}%"
            return f"{v:.1f}x" if abs(v) < 1000 else f"${v/1e9:.1f}B"

        peer_rows = "\n".join([
            f"  {p.ticker}: P/E={_fmt(p.pe_ratio)} EV/EBITDA={_fmt(p.ev_ebitda)} "
            f"GrossMargin={_fmt(p.gross_margin, True)} RevGrowth={_fmt(p.revenue_growth_yoy, True)}"
            for p in peer_table.peers
        ])

        prompt = f"""Subject: {state.company_name or ticker} ({ticker})
  P/E={_fmt(subject.pe_ratio)} EV/EBITDA={_fmt(subject.ev_ebitda)}
  Gross Margin={_fmt(subject.gross_margin, True)} Rev Growth={_fmt(subject.revenue_growth_yoy, True)}
  Market Cap={_fmt(subject.market_cap)}

Peers:
{peer_rows}

Research focus: {state.research_brief}

Provide a peer comparison valuation analysis."""

        analysis = await self.llm(prompt, SYSTEM_PROMPT, state, max_tokens=1000)

        return state.model_copy(update={
            "fundamentals": subject,
            "peer_comparison": peer_table,
            "agent_outputs": {
                **state.agent_outputs,
                "comps": {
                    "summary": analysis,
                    "peers_analysed": len(peer_table.peers),
                    "subject_pe": subject.pe_ratio,
                    "subject_ev_ebitda": subject.ev_ebitda,
                },
            },
        })


comps_agent = CompsAgent()


async def comps_node(state: ResearchState) -> ResearchState:
    return await comps_agent(state)
