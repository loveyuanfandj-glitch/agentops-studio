from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agentops.config import Settings
from agentops.models import AgentRun, Conversation, RunStep
from agentops.observability import tracer
from agentops.pricing import estimate_cost
from agentops.providers import AgentProvider, ProviderError
from agentops.repository import Repository
from agentops.tools import ToolError, ToolRegistry

logger = logging.getLogger(__name__)

AGENT_INSTRUCTIONS = """You are the operations copilot for a multi-tenant commerce platform.
Use tools whenever business data is needed. Gather all required evidence before answering.
Never invent metrics. Clearly state recommended actions and cite the relevant entity IDs.
Keep the final response concise, decision-oriented, and grounded in tool results."""


class GuardrailTriggered(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AgentOrchestrator:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: AgentProvider,
        tools: ToolRegistry,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider
        self.tools = tools
        self.repository = Repository(session)

    async def run(
        self, conversation: Conversation, tenant_id: str, prompt: str
    ) -> AgentRun:
        history = [
            {"role": message.role, "content": message.content}
            for message in conversation.messages
        ]
        await self.repository.add_message(conversation.id, "user", prompt)
        run = AgentRun(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            model=self.settings.openai_model,
            prompt=prompt,
            cost_usd=Decimal(0),
            steps=[],
        )
        self.session.add(run)
        await self.session.flush()

        input_items: list[dict[str, Any]] = [*history, {"role": "user", "content": prompt}]
        started = perf_counter()
        try:
            async with asyncio.timeout(self.settings.run_timeout_seconds):
                await self._execute_loop(run, tenant_id, input_items)
        except GuardrailTriggered as exc:
            run.status = "guarded"
            run.guardrail_reason = exc.reason
            run.answer = f"Run stopped by a safety guard: {exc.reason}."
        except TimeoutError:
            run.status = "failed"
            run.error_code = "run_timeout"
            run.answer = "The agent exceeded its execution deadline."
        except ProviderError as exc:
            run.status = "failed"
            run.error_code = exc.code
            run.answer = "The model provider could not complete this run."
        except Exception:
            logger.exception("agent_run_failed", extra={"run_id": run.id, "tenant_id": tenant_id})
            run.status = "failed"
            run.error_code = "internal_error"
            run.answer = "The agent encountered an unexpected internal error."

        if run.answer:
            await self.repository.add_message(conversation.id, "assistant", run.answer)
        run.steps_count = len(run.steps)
        run.latency_ms = round((perf_counter() - started) * 1000)
        run.completed_at = datetime.now(UTC)
        conversation.updated_at = run.completed_at
        await self.session.commit()
        persisted = await self.repository.get_run(run.id, tenant_id)
        if persisted is None:
            raise RuntimeError("Persisted run could not be loaded")
        return persisted

    async def _execute_loop(
        self, run: AgentRun, tenant_id: str, input_items: list[dict[str, Any]]
    ) -> None:
        repeated_calls: Counter[str] = Counter()
        sequence = 0
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("agent.run_id", run.id)
            span.set_attribute("tenant.id", tenant_id)
            for model_step in range(1, self.settings.max_agent_steps + 1):
                with tracer.start_as_current_span("agent.model_turn") as model_span:
                    model_span.set_attribute("agent.step", model_step)
                    turn_started = perf_counter()
                    turn = await self.provider.respond(
                        input_items, self.tools.schemas(), AGENT_INSTRUCTIONS
                    )
                    model_duration = round((perf_counter() - turn_started) * 1000)

                run.input_tokens += turn.usage.input_tokens
                run.output_tokens += turn.usage.output_tokens
                run.cached_tokens += turn.usage.cached_tokens
                run.cost_usd += estimate_cost(
                    self.settings.openai_model,
                    turn.usage.input_tokens,
                    turn.usage.output_tokens,
                )
                sequence += 1
                run.steps.append(
                    RunStep(
                        sequence=sequence,
                        kind="model",
                        name=self.settings.openai_model,
                        status="completed",
                        duration_ms=model_duration,
                        output={
                            "tool_calls": [call.name for call in turn.tool_calls],
                            "has_final_answer": bool(turn.final_text),
                            "usage": {
                                "input_tokens": turn.usage.input_tokens,
                                "output_tokens": turn.usage.output_tokens,
                                "cached_tokens": turn.usage.cached_tokens,
                            },
                        },
                    )
                )
                if float(run.cost_usd) > self.settings.run_budget_usd:
                    raise GuardrailTriggered(
                        f"estimated run cost exceeded ${self.settings.run_budget_usd:.2f}"
                    )

                input_items.extend(turn.output_items)
                if turn.tool_calls:
                    for tool_call in turn.tool_calls:
                        serialized_arguments = json.dumps(tool_call.arguments, sort_keys=True)
                        signature = f"{tool_call.name}:{serialized_arguments}"
                        repeated_calls[signature] += 1
                        if repeated_calls[signature] > self.settings.max_repeated_tool_calls:
                            raise GuardrailTriggered(
                                f"repeated tool call detected for {tool_call.name}"
                            )
                        sequence += 1
                        await self._execute_tool(
                            run, sequence, tenant_id, tool_call.call_id, tool_call.name,
                            tool_call.arguments, input_items
                        )
                    continue

                if turn.final_text:
                    run.status = "succeeded"
                    run.answer = turn.final_text
                    return
                raise ProviderError(
                    "empty_provider_response", "Model returned no tool call or final answer"
                )

        raise GuardrailTriggered(f"maximum of {self.settings.max_agent_steps} model steps reached")

    async def _execute_tool(
        self,
        run: AgentRun,
        sequence: int,
        tenant_id: str,
        call_id: str,
        name: str,
        arguments: dict[str, Any],
        input_items: list[dict[str, Any]],
    ) -> None:
        with tracer.start_as_current_span(f"agent.tool.{name}") as span:
            span.set_attribute("tool.name", name)
            try:
                execution = await self.tools.execute(name, arguments, tenant_id)
                output = {"ok": True, "data": execution.output}
                run.steps.append(
                    RunStep(
                        sequence=sequence,
                        kind="tool",
                        name=name,
                        status="completed",
                        arguments=arguments,
                        output=execution.output,
                        duration_ms=execution.duration_ms,
                    )
                )
            except ToolError as exc:
                output = {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
                run.steps.append(
                    RunStep(
                        sequence=sequence,
                        kind="tool",
                        name=name,
                        status="failed",
                        arguments=arguments,
                        output=output,
                        error_code=exc.code,
                    )
                )
                span.record_exception(exc)
        input_items.append(
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(output),
            }
        )
