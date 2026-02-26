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
import re
import time
from typing import Dict, Optional

from agents.oleg.orchestrator.chain import (
    AgentStep, ChainResult, OrchestratorDecision, MAX_CHAIN_STEPS,
)
from agents.oleg.orchestrator.prompts import (
    DECIDE_NEXT_STEP_PROMPT,
    REVIEW_SYNTHESIS_PROMPT,
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
        review_model: Optional[str] = None,
        review_task_types: Optional[list] = None,
        review_max_tokens: int = 16000,
        review_mode: str = "dry_run",
    ):
        self.llm = llm_client
        self.model = model
        self.agents = agents  # {"reporter": ReporterAgent, "researcher": ..., "quality": ...}
        self.pricing = pricing or {}
        self.max_chain_steps = max_chain_steps
        self.anomaly_margin_threshold = anomaly_margin_threshold
        self.anomaly_drr_threshold = anomaly_drr_threshold
        self.review_model = review_model
        self.review_task_types = review_task_types or []
        self.review_max_tokens = review_max_tokens
        self.review_mode = review_mode

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

        # Multi-model review (optional, per task_type)
        review_issues = 0
        review_notes = ""
        if self.review_model and task_type in self.review_task_types:
            reviewed = await self._review_synthesis(
                synthesis, chain_history, task, task_type,
            )
            review_cost = reviewed.get("review_cost", 0.0)
            review_issues = reviewed.get("issues_found", 0)
            review_notes = reviewed.get("review_notes", "")
            total_cost += review_cost

            if review_issues > 0:
                logger.info(f"Review found {review_issues} issues: {review_notes}")

            # Only replace synthesis in active mode
            if self.review_mode == "active" and review_issues > 0:
                synthesis["brief_summary"] = reviewed["brief_summary"]
                synthesis["detailed_report"] = reviewed["detailed_report"]
                logger.info("Review: applied corrections to synthesis")
            elif self.review_mode == "dry_run" and review_issues > 0:
                logger.info("Review (dry-run): issues found but NOT applied")

        total_duration = int((time.time() - start_time) * 1000)

        return ChainResult(
            summary=synthesis.get("brief_summary", ""),
            detailed=synthesis.get("detailed_report"),
            steps=chain_history,
            total_steps=len(chain_history),
            total_cost=total_cost,
            total_duration_ms=total_duration,
            task_type=task_type,
            review_issues_found=review_issues,
            review_notes=review_notes,
        )

    async def _decide_next_step(
        self,
        task: str,
        task_type: str,
        chain_history: list[AgentStep],
        step: int,
    ) -> OrchestratorDecision:
        """Use LLM to decide the next step in the chain."""

        # Shortcut for first step of reports (scheduled or custom)
        if step == 0 and task_type in ("daily", "weekly", "monthly", "custom"):
            return OrchestratorDecision(
                done=False,
                next_agent="reporter",
                instruction=task,
                reasoning="Report always starts with Reporter",
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
                max_tokens=1000,
                response_format={"type": "json_object"},
            )

            content = response.get("content") or ""
            if not content.strip():
                finish_reason = response.get("finish_reason", "unknown")
                logger.warning(
                    f"Orchestrator got empty response (finish_reason={finish_reason}), "
                    f"synthesizing from collected data"
                )
                return OrchestratorDecision(
                    done=True,
                    reasoning=f"Empty LLM response (finish_reason={finish_reason}), synthesizing",
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

    @staticmethod
    def _parse_report_sections(content: str) -> dict:
        """Parse LLM output into brief_summary and detailed_report sections.

        Looks for markers like '# brief_summary' and '# detailed_report'.
        If not found, uses the first ~4000 chars as brief and full text as detailed.
        """
        brief = ""
        detailed = ""

        # Try to split by section headers (case-insensitive, flexible whitespace)
        brief_pattern = re.compile(
            r'^#+\s*brief[_\s]?summary\s*$', re.IGNORECASE | re.MULTILINE,
        )
        detailed_pattern = re.compile(
            r'^#+\s*detailed[_\s]?report\s*$', re.IGNORECASE | re.MULTILINE,
        )

        brief_match = brief_pattern.search(content)
        detailed_match = detailed_pattern.search(content)

        if brief_match and detailed_match:
            # Both sections found — extract each
            if brief_match.start() < detailed_match.start():
                brief = content[brief_match.end():detailed_match.start()].strip()
                detailed = content[detailed_match.end():].strip()
            else:
                detailed = content[detailed_match.end():brief_match.start()].strip()
                brief = content[brief_match.end():].strip()
        elif brief_match:
            # Only brief found — everything after it is brief, no detailed
            brief = content[brief_match.end():].strip()
            detailed = content
        elif detailed_match:
            # Only detailed found — everything before it is brief
            brief = content[:detailed_match.start()].strip()
            detailed = content[detailed_match.end():].strip()
        else:
            # No markers — use first ~4000 chars as brief
            brief = content[:4000].strip()
            detailed = content

        return {
            "brief_summary": brief or content[:4000],
            "detailed_report": detailed or content,
        }

    async def _synthesize(
        self, task: str, chain_history: list[AgentStep],
    ) -> dict:
        """Synthesize final answer from chain results."""

        # If only one step and it's reporter — use its output directly
        if len(chain_history) == 1 and chain_history[0].agent == "reporter":
            return self._parse_report_sections(chain_history[0].result)

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

            return self._parse_report_sections(content)

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            # Fallback: concatenate results
            combined = "\n\n---\n\n".join(
                f"[{s.agent}]: {s.result}" for s in chain_history
            )
            return {
                "brief_summary": combined[:4000],
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

    # ── Multi-model review ────────────────────────────────────────

    async def _review_synthesis(
        self,
        synthesis: dict,
        chain_history: list[AgentStep],
        task: str,
        task_type: str,
    ) -> dict:
        """Review and correct synthesis using a different model (e.g. Gemini).

        Returns dict with brief_summary, detailed_report, review_cost,
        issues_found, review_notes. On any error returns original synthesis.
        """
        brief = synthesis.get("brief_summary", "")
        detailed = synthesis.get("detailed_report", "")
        chain_data = self._format_chain_history_full(chain_history)

        prompt = REVIEW_SYNTHESIS_PROMPT.format(
            task=task,
            chain_data=chain_data,
            brief_summary=brief,
            detailed_report=detailed,
        )

        try:
            response = await self.llm.complete(
                messages=[
                    {"role": "system", "content": "Ты — ревьюер. Ответь строго в JSON."},
                    {"role": "user", "content": prompt},
                ],
                model=self.review_model,
                temperature=0.2,
                max_tokens=self.review_max_tokens,
                response_format={"type": "json_object"},
            )

            review_cost = self._calc_review_cost(response.get("usage", {}))
            content = response.get("content") or ""

            if not content.strip():
                logger.warning("Review returned empty response, keeping original")
                return {
                    "brief_summary": brief,
                    "detailed_report": detailed,
                    "review_cost": review_cost,
                    "issues_found": 0,
                    "review_notes": "Empty review response",
                }

            review_data = json.loads(content)
            return {
                "brief_summary": review_data.get("brief_summary", brief),
                "detailed_report": review_data.get("detailed_report", detailed),
                "review_cost": review_cost,
                "issues_found": review_data.get("issues_found", 0),
                "review_notes": review_data.get("review_notes", ""),
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Review JSON parse failed: {e}, keeping original")
            return {
                "brief_summary": brief,
                "detailed_report": detailed,
                "review_cost": 0.0,
                "issues_found": 0,
                "review_notes": f"JSON parse failed: {e}",
            }
        except Exception as e:
            logger.error(f"Review failed: {e}, keeping original")
            return {
                "brief_summary": brief,
                "detailed_report": detailed,
                "review_cost": 0.0,
                "issues_found": 0,
                "review_notes": f"Review error: {e}",
            }

    def _format_chain_history_full(self, history: list[AgentStep]) -> str:
        """Format chain history WITHOUT truncation — for review validation."""
        if not history:
            return ""

        parts = []
        for i, step in enumerate(history, 1):
            parts.append(
                f"Шаг {i} [{step.agent}]:\n"
                f"Инструкция: {step.instruction}\n"
                f"Результат ({step.iterations} итераций, ${step.cost_usd:.4f}):\n"
                f"{step.result}"
            )
        return "\n\n---\n\n".join(parts)

    def _calc_review_cost(self, usage: dict) -> float:
        """Calculate cost of the review LLM call."""
        if not self.review_model or not usage:
            return 0.0
        default_rate = {"input": 0.001, "output": 0.001}
        rates = self.pricing.get(self.review_model, default_rate)
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        return round(
            (input_tokens / 1000) * rates["input"]
            + (output_tokens / 1000) * rates["output"],
            6,
        )
