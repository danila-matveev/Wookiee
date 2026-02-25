"""
OlegOrchestrator — collaborative chain between sub-agents.

Oleg (LLM) decides at each step:
- Who to call next (reporter, researcher, quality)
- What instruction to give
- When to stop and synthesize

Chain patterns:
- Daily report (no anomaly): Reporter → synthesize (1 step)
- Daily report (anomaly): Reporter → Researcher → Reporter verify → synthesize (3 steps)
- Weekly report: Reporter → Researcher → Reporter verify → synthesize (3 steps)
- User query: Oleg routes dynamically
- Feedback: Quality → Reporter verify → Quality decide → synthesize
"""
import json
import logging
import time
from typing import Dict, Optional

from agents.oleg.orchestrator.chain import (
    AgentStep, ChainResult, OrchestratorDecision, MAX_CHAIN_STEPS,
)
from agents.oleg.orchestrator.prompts import (
    DECIDE_NEXT_STEP_PROMPT,
    SYNTHESIZE_PROMPT,
)

logger = logging.getLogger(__name__)


class OlegOrchestrator:
    """Oleg orchestrates collaborative chains between sub-agents."""

    def __init__(
        self,
        llm_client,
        model: str,
        agents: Dict,
        pricing: Optional[dict] = None,
        max_chain_steps: int = MAX_CHAIN_STEPS,
        anomaly_margin_threshold: float = 10.0,
        anomaly_drr_threshold: float = 30.0,
    ):
        self.llm = llm_client
        self.model = model
        self.agents = agents  # {"reporter": ReporterAgent, "researcher": ..., "quality": ...}
        self.pricing = pricing or {}
        self.max_chain_steps = max_chain_steps
        self.anomaly_margin_threshold = anomaly_margin_threshold
        self.anomaly_drr_threshold = anomaly_drr_threshold

    async def run_chain(
        self, task: str, task_type: str, context: dict = None,
    ) -> ChainResult:
        """
        Run a collaborative chain.

        For scheduled reports (daily/weekly): starts with Reporter, escalates if anomaly.
        For user queries: Oleg decides the chain dynamically.
        For feedback: starts with Quality.
        """
        start_time = time.time()
        chain_history: list[AgentStep] = []
        total_cost = 0.0

        for step in range(self.max_chain_steps):
            # Decide next step
            decision = await self._decide_next_step(
                task=task,
                task_type=task_type,
                chain_history=chain_history,
                step=step,
            )

            if decision.done:
                logger.info(
                    f"Orchestrator: done at step {step + 1}, "
                    f"reason: {decision.reasoning}"
                )
                break

            # Validate agent exists
            agent_name = decision.next_agent
            agent = self.agents.get(agent_name)
            if not agent:
                logger.warning(
                    f"Orchestrator requested unknown agent '{agent_name}', "
                    f"available: {list(self.agents.keys())}"
                )
                # Fall back to reporter
                agent_name = "reporter"
                agent = self.agents.get(agent_name)
                if not agent:
                    break

            # Build context from chain history
            chain_context = self._build_chain_context(chain_history)

            # Execute agent
            logger.info(
                f"Orchestrator step {step + 1}/{self.max_chain_steps}: "
                f"{agent_name} ← {decision.instruction[:100]}..."
            )

            agent_start = time.time()
            result = await agent.analyze(
                instruction=decision.instruction,
                context=chain_context,
            )
            agent_duration = int((time.time() - agent_start) * 1000)

            # Record step
            chain_history.append(AgentStep(
                agent=agent_name,
                instruction=decision.instruction,
                result=result.content,
                cost_usd=result.total_cost,
                duration_ms=agent_duration,
                iterations=result.iterations,
            ))
            total_cost += result.total_cost

        # Synthesize final answer
        synthesis = await self._synthesize(task, chain_history)
        total_duration = int((time.time() - start_time) * 1000)

        return ChainResult(
            summary=synthesis.get("brief_summary", ""),
            detailed=synthesis.get("detailed_report"),
            steps=chain_history,
            total_steps=len(chain_history),
            total_cost=total_cost,
            total_duration_ms=total_duration,
            task_type=task_type,
        )

    async def _decide_next_step(
        self,
        task: str,
        task_type: str,
        chain_history: list[AgentStep],
        step: int,
    ) -> OrchestratorDecision:
        """Use LLM to decide the next step in the chain."""

        # Shortcut for first step of scheduled reports
        if step == 0 and task_type in ("daily", "weekly", "monthly"):
            return OrchestratorDecision(
                done=False,
                next_agent="reporter",
                instruction=task,
                reasoning="Scheduled report always starts with Reporter",
            )

        # Shortcut for feedback
        if step == 0 and task_type == "feedback":
            return OrchestratorDecision(
                done=False,
                next_agent="quality",
                instruction=task,
                reasoning="Feedback always starts with Quality Agent",
            )

        # Shortcut: if only reporter exists and we already have 1 step, synthesize
        if len(self.agents) == 1 and step >= 1:
            return OrchestratorDecision(
                done=True,
                reasoning="Only reporter agent available, synthesizing after 1 step",
            )

        # LLM decides
        chain_history_text = self._format_chain_history(chain_history)

        prompt = DECIDE_NEXT_STEP_PROMPT.format(
            task=task,
            task_type=task_type,
            step=step + 1,
            max_steps=self.max_chain_steps,
            chain_history=chain_history_text or "Пока пусто — это первый шаг.",
            margin_threshold=self.anomaly_margin_threshold,
            drr_threshold=self.anomaly_drr_threshold,
        )

        try:
            response = await self.llm.complete(
                messages=[
                    {"role": "system", "content": "Ты — оркестратор. Ответь строго в JSON."},
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
                temperature=0.2,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            content = response.get("content") or ""
            if not content.strip():
                finish_reason = response.get("finish_reason", "unknown")
                logger.warning(
                    f"Orchestrator got empty response (finish_reason={finish_reason}), "
                    f"continuing with next reporter step"
                )
                return OrchestratorDecision(
                    done=False,
                    next_agent="reporter",
                    instruction=task,
                    reasoning=f"Empty LLM response (finish_reason={finish_reason}), continuing",
                )

            decision_data = json.loads(content)

            return OrchestratorDecision(
                done=decision_data.get("done", False),
                next_agent=decision_data.get("next_agent", "reporter"),
                instruction=decision_data.get("instruction", task),
                reasoning=decision_data.get("reasoning", ""),
            )

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Orchestrator decision failed: {e}, defaulting to done=True")
            return OrchestratorDecision(
                done=True,
                reasoning=f"Decision failed: {e}, synthesizing from collected data",
            )

    async def _synthesize(
        self, task: str, chain_history: list[AgentStep],
    ) -> dict:
        """Synthesize final answer from chain results."""

        # If only one step and it's reporter — use its output directly
        if len(chain_history) == 1 and chain_history[0].agent == "reporter":
            return {
                "brief_summary": chain_history[0].result,
                "detailed_report": chain_history[0].result,
            }

        chain_results_text = self._format_chain_history(chain_history)

        prompt = SYNTHESIZE_PROMPT.format(
            task=task,
            chain_results=chain_results_text,
            caveats_section="",
        )

        try:
            response = await self.llm.complete(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Синтезируй финальный отчёт."},
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=16000,
            )

            content = response.get("content", "")

            return {
                "brief_summary": content,
                "detailed_report": content,
            }

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            # Fallback: concatenate results
            combined = "\n\n---\n\n".join(
                f"[{s.agent}]: {s.result}" for s in chain_history
            )
            return {
                "brief_summary": combined[:16000],
                "detailed_report": combined,
            }

    def _format_chain_history(self, history: list[AgentStep]) -> str:
        """Format chain history for LLM context."""
        if not history:
            return ""

        parts = []
        for i, step in enumerate(history, 1):
            parts.append(
                f"Шаг {i} [{step.agent}]:\n"
                f"Инструкция: {step.instruction}\n"
                f"Результат ({step.iterations} итераций, ${step.cost_usd:.4f}):\n"
                f"{step.result[:3000]}"
            )
        return "\n\n---\n\n".join(parts)

    def _build_chain_context(self, history: list[AgentStep]) -> str:
        """Build context string from previous steps for the next agent."""
        if not history:
            return ""

        parts = []
        for step in history:
            parts.append(
                f"[{step.agent}]: {step.result[:2000]}"
            )
        return "\n\n".join(parts)
