"""
VERITY — LangGraph Graph Definition
Defines the agent graph, state transitions, and execution order.
Parallel execution where possible, sequential where dependencies exist.

Pipeline:
  orchestrator
      ↓ (parallel)
  filing | earnings | comps | news
      ↓ (join)
  synthesis
      ↓
  critique
      ↓
  citation
      ↓
  [done]
"""

from typing import Annotated, Any

import structlog
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.agents.citation_agent import citation_node
from app.agents.comps_agent import comps_node
from app.agents.critique_agent import critique_node
from app.agents.earnings_agent import earnings_node
from app.agents.filing_agent import filing_node
from app.agents.news_agent import news_node
from app.agents.orchestrator import orchestrator_node
from app.agents.synthesis_agent import synthesis_node
from app.models.schemas import ResearchState

logger = structlog.get_logger(__name__)


def _route_after_orchestrator(state: ResearchState) -> list[str]:
    """
    After the orchestrator runs, decide which agents to fan out to in parallel.
    If the orchestrator failed, go straight to END.
    """
    if state.errors.get("orchestrator"):
        logger.error("orchestrator_failed_routing_to_end", error=state.errors["orchestrator"])
        return [END]

    # Always run all four data-gathering agents in parallel
    return ["filing_node", "earnings_node", "comps_node", "news_node"]


def _route_after_parallel(state: ResearchState) -> str:
    """After all parallel agents complete, always proceed to synthesis."""
    return "synthesis_node"


def build_research_graph() -> StateGraph:
    """
    Build and compile the VERITY LangGraph research pipeline.
    Returns a compiled graph ready to invoke.
    """
    graph = StateGraph(ResearchState)

    # Register all nodes
    graph.add_node("orchestrator_node", orchestrator_node)
    graph.add_node("filing_node", filing_node)
    graph.add_node("earnings_node", earnings_node)
    graph.add_node("comps_node", comps_node)
    graph.add_node("news_node", news_node)
    graph.add_node("synthesis_node", synthesis_node)
    graph.add_node("critique_node", critique_node)
    graph.add_node("citation_node", citation_node)

    # Entry point
    graph.set_entry_point("orchestrator_node")

    # Orchestrator fans out to parallel data agents
    graph.add_conditional_edges(
        "orchestrator_node",
        _route_after_orchestrator,
        {
            "filing_node": "filing_node",
            "earnings_node": "earnings_node",
            "comps_node": "comps_node",
            "news_node": "news_node",
            END: END,
        },
    )

    # All parallel agents converge at synthesis
    for node in ["filing_node", "earnings_node", "comps_node", "news_node"]:
        graph.add_edge(node, "synthesis_node")

    # Linear pipeline after synthesis
    graph.add_edge("synthesis_node", "critique_node")
    graph.add_edge("critique_node", "citation_node")
    graph.add_edge("citation_node", END)

    return graph.compile()


# Compiled graph — import this in the Celery task
research_graph = build_research_graph()
