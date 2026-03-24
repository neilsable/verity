"""
VERITY — Base Agent
Every agent inherits from this. Provides:
- LLM call with timeout, retry, fallback model
- Token and cost tracking per call
- Structured error handling — agents never crash the pipeline
- State update helpers
- Structured logging with agent context
"""

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

import structlog
from anthropic import AsyncAnthropic, APIStatusError, APITimeoutError
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.models.schemas import AgentName, ResearchState

logger = structlog.get_logger(__name__)
settings = get_settings()

_anthropic_client: AsyncAnthropic | None = None
_openai_client: AsyncOpenAI | None = None


def get_anthropic() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
    return _anthropic_client


def get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
    return _openai_client


class BaseAgent(ABC):
    """
    Base class for all VERITY agents.
    Subclasses implement `run(state)` and call `self.llm(prompt, system)`.
    """

    name: AgentName

    def __init__(self) -> None:
        self.log = logger.bind(agent=self.name)

    async def __call__(self, state: ResearchState) -> ResearchState:
        """
        Entry point called by LangGraph.
        Wraps run() with timing, error handling, and progress publishing.
        """
        self.log.info("agent_started", job_id=str(state.job_id), ticker=state.ticker)
        start = time.perf_counter()

        try:
            updated_state = await self.run(state)
            duration_ms = round((time.perf_counter() - start) * 1000)
            self.log.info("agent_completed", duration_ms=duration_ms, job_id=str(state.job_id))
            await self._publish_progress(state, "completed", duration_ms)
            return updated_state

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000)
            self.log.exception("agent_failed", error=str(exc), duration_ms=duration_ms)
            await self._publish_progress(state, "failed", duration_ms, error=str(exc))

            # Record error in state but DO NOT re-raise — pipeline continues
            new_errors = {**state.errors, self.name: str(exc)}
            return state.model_copy(update={"errors": new_errors})

    @abstractmethod
    async def run(self, state: ResearchState) -> ResearchState:
        """Implement the agent's core logic here."""
        ...

    async def llm(
        self,
        prompt: str,
        system: str,
        state: ResearchState,
        max_tokens: int | None = None,
        use_fallback: bool = False,
    ) -> str:
        """
        Make an LLM call with retry, fallback, and cost tracking.
        Always use this method — never call the LLM client directly.
        """
        max_tokens = max_tokens or settings.llm_max_tokens

        if use_fallback:
            return await self._call_openai(prompt, system, state, max_tokens)
        else:
            try:
                return await self._call_anthropic(prompt, system, state, max_tokens)
            except (APIStatusError, APITimeoutError, Exception) as e:
                self.log.warning(
                    "primary_llm_failed_falling_back",
                    error=str(e),
                    fallback=settings.llm_fallback_model,
                )
                return await self._call_openai(prompt, system, state, max_tokens)

    @retry(
        retry=retry_if_exception_type((APIStatusError, APITimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
    )
    async def _call_anthropic(
        self,
        prompt: str,
        system: str,
        state: ResearchState,
        max_tokens: int,
    ) -> str:
        client = get_anthropic()
        response = await client.messages.create(
            model=settings.llm_primary_model,
            max_tokens=max_tokens,
            temperature=settings.llm_temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = settings.anthropic_cost_usd(input_tokens, output_tokens)

        self._track_tokens(state, settings.llm_primary_model, input_tokens, output_tokens, cost)

        content = response.content[0]
        if content.type != "text":
            raise ValueError(f"Unexpected response type: {content.type}")

        return content.text

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_openai(
        self,
        prompt: str,
        system: str,
        state: ResearchState,
        max_tokens: int,
    ) -> str:
        client = get_openai()
        response = await client.chat.completions.create(
            model=settings.llm_fallback_model,
            max_tokens=max_tokens,
            temperature=settings.llm_temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        cost = settings.openai_cost_usd(input_tokens, output_tokens)

        self._track_tokens(state, settings.llm_fallback_model, input_tokens, output_tokens, cost)

        return response.choices[0].message.content or ""

    def _track_tokens(
        self,
        state: ResearchState,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """Update token usage in state. Called after every LLM call."""
        agent_key = str(self.name)
        current = state.token_usage.get(agent_key, {"input": 0, "output": 0, "cost_usd": 0.0})
        state.token_usage[agent_key] = {
            "input": current["input"] + input_tokens,
            "output": current["output"] + output_tokens,
            "cost_usd": round(current["cost_usd"] + cost_usd, 6),
            "model": model,
        }
        state.total_cost_usd = round(state.total_cost_usd + cost_usd, 6)

        self.log.info(
            "llm_call_tracked",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd, 6),
            total_cost_usd=state.total_cost_usd,
        )

    async def _publish_progress(
        self,
        state: ResearchState,
        status: str,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        """Publish agent progress to Redis pub/sub for SSE streaming."""
        try:
            from app.services.cache import publish_job_progress
            event: dict[str, Any] = {
                "event": f"agent_{status}",
                "agent": str(self.name),
                "job_id": str(state.job_id),
                "duration_ms": duration_ms,
            }
            if error:
                event["error"] = error
            await publish_job_progress(str(state.job_id), event)
        except Exception:
            pass  # Never let progress publishing crash the pipeline
