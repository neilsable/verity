"""
VERITY — Orchestrator Agent
Receives ticker + research brief, validates the company, resolves metadata,
and prepares the shared state for all downstream agents.
"""

import structlog

from app.agents.base import BaseAgent
from app.models.schemas import AgentName, ResearchState

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are the orchestrator of an autonomous equity research platform.
Your job is to analyse a research brief, identify the key questions to answer,
and extract the company name from the ticker symbol provided.

Respond in this exact format — no preamble, no extra text:

COMPANY_NAME: <full legal company name>
SECTOR: <sector>
KEY_QUESTIONS:
1. <question 1>
2. <question 2>
3. <question 3>
4. <question 4>
5. <question 5>"""


class OrchestratorAgent(BaseAgent):
    name = AgentName.ORCHESTRATOR

    async def run(self, state: ResearchState) -> ResearchState:
        prompt = f"""Ticker: {state.ticker}
Research brief: {state.research_brief}

Identify the company name, sector, and the 5 most important questions
this research brief is asking us to answer."""

        response = await self.llm(prompt, SYSTEM_PROMPT, state, max_tokens=512)

        # Parse response
        company_name = state.ticker  # fallback
        key_questions: list[str] = []

        for line in response.splitlines():
            line = line.strip()
            if line.startswith("COMPANY_NAME:"):
                company_name = line.split(":", 1)[1].strip()
            elif line and line[0].isdigit() and "." in line:
                question = line.split(".", 1)[1].strip()
                if question:
                    key_questions.append(question)

        self.log.info(
            "orchestrator_parsed",
            company_name=company_name,
            questions=len(key_questions),
        )

        return state.model_copy(update={
            "company_name": company_name,
            "agent_outputs": {
                **state.agent_outputs,
                "orchestrator": {
                    "company_name": company_name,
                    "key_questions": key_questions,
                    "raw_response": response,
                },
            },
        })


# LangGraph node function
orchestrator_agent = OrchestratorAgent()


async def orchestrator_node(state: ResearchState) -> ResearchState:
    return await orchestrator_agent(state)
