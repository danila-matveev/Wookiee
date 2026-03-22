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
- Marketing daily/weekly: Marketer → synthesize (1 step)
- Marketing monthly: Marketer → Researcher → synthesize (2-3 steps)
- Financial + DRR anomaly: Reporter → Marketer → synthesize (2 steps)
- User query: Oleg routes dynamically
- Feedback: Quality → Reporter verify → Quality decide → synthesize
"""
import json
import logging
import re
import time
from datetime import date
from typing import Dict, Optional

from agents.oleg.orchestrator.chain import (
    AgentStep, ChainResult, OrchestratorDecision, MAX_CHAIN_STEPS,
)
from shared.signals import detect_signals
from agents.oleg.orchestrator.prompts import (
    DECIDE_NEXT_STEP_PROMPT,
    REVIEW_SYNTHESIS_PROMPT,
    SYNTHESIZE_PROMPT,
)

logger = logging.getLogger(__name__)

# Tool name -> signal source tag
SOURCE_MAP = {
    "get_plan_vs_fact": "plan_vs_fact",
    "get_brand_finance": "brand_finance",
    "get_margin_levers": "margin_levers",
    "get_advertising_stats": "advertising",
    "get_model_breakdown": "model_breakdown",
}


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
        self._agent_results: dict = {}  # runtime only, not serialized

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
        self._agent_results.clear()

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

            # Save full AgentResult for structured_data extraction
            self._agent_results[agent_name] = result

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

        # --- Advisor chain: detect signals and generate recommendations ---
        if chain_history:
            structured_data = {}
            for step_entry in chain_history:
                if step_entry.agent in ("reporter", "marketer", "funnel"):
                    agent_result = self._agent_results.get(step_entry.agent)
                    if agent_result:
                        extracted = self._extract_structured_data(agent_result)
                        structured_data.update(extracted)

            if structured_data:
                report_type = "daily"
                if "weekly" in task_type:
                    report_type = "weekly"
                elif "monthly" in task_type:
                    report_type = "monthly"

                try:
                    advisor_result = await self._run_advisor_chain(
                        structured_data=structured_data,
                        report_type=report_type,
                        chain_history=chain_history,
                    )
                    if advisor_result.get("recommendations"):
                        chain_history.append(AgentStep(
                            agent="advisor_chain",
                            instruction="Signal Detection → Advisor → Validator",
                            result=json.dumps(advisor_result, ensure_ascii=False, default=str),
                            cost_usd=0.0,
                            duration_ms=0,
                            iterations=0,
                        ))
                except Exception as e:
                    logger.warning(f"Advisor chain failed: {e}")

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
            telegram_summary=synthesis.get("telegram_summary", ""),
            steps=chain_history,
            total_steps=len(chain_history),
            total_cost=total_cost,
            total_duration_ms=total_duration,
            task_type=task_type,
            review_issues_found=review_issues,
            review_notes=review_notes,
        )

    # KB consultation instruction injected into every report task
    _KB_INSTRUCTION_PREFIX = (
        "ОБЯЗАТЕЛЬНО: Перед формированием рекомендаций и гипотез вызови "
        "search_knowledge_base с 2-3 релевантными запросами по ключевым темам "
        "анализа. Используй найденные знания как основу для секции "
        "«Гипотезы → Действия». Без KB-консультации отчёт НЕ считается полным.\n\n"
    )

    async def _decide_next_step(
        self,
        task: str,
        task_type: str,
        chain_history: list[AgentStep],
        step: int,
    ) -> OrchestratorDecision:
        """Use LLM to decide the next step in the chain."""

        # Funnel reports → funnel agent (Макар)
        if step == 0 and task_type.startswith("funnel_"):
            return OrchestratorDecision(
                done=False,
                next_agent="funnel",
                instruction=self._KB_INSTRUCTION_PREFIX + task,
                reasoning="Funnel report → Funnel agent (Макар), KB consultation required",
            )

        # Shortcut for first step of marketing reports
        if step == 0 and task_type.startswith("marketing_"):
            return OrchestratorDecision(
                done=False,
                next_agent="marketer",
                instruction=self._KB_INSTRUCTION_PREFIX + task,
                reasoning="Marketing report always starts with Marketer, KB consultation required",
            )

        # Shortcut for first step of financial reports (scheduled or custom)
        if step == 0 and task_type in ("daily", "weekly", "monthly", "custom"):
            return OrchestratorDecision(
                done=False,
                next_agent="reporter",
                instruction=self._KB_INSTRUCTION_PREFIX + task,
                reasoning="Report always starts with Reporter, KB consultation required",
            )

        # Shortcut for feedback
        if step == 0 and task_type == "feedback":
            return OrchestratorDecision(
                done=False,
                next_agent="quality",
                instruction=task,
                reasoning="Feedback always starts with Quality Agent",
            )

        # KB management → Christina
        if step == 0 and task_type.startswith("kb_"):
            return OrchestratorDecision(
                done=False,
                next_agent="christina",
                instruction=task,
                reasoning="KB management task → Christina",
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
        """Parse LLM output into telegram_summary, brief_summary and detailed_report.

        Looks for markers like '# telegram_summary', '# brief_summary',
        '# detailed_report'. If not found, uses heuristic fallbacks.
        """
        telegram = ""
        brief = ""
        detailed = ""

        # Try to split by section headers (case-insensitive, flexible whitespace).
        # Matches variations like: # brief_summary, ## BRIEF SUMMARY,
        # ## 📊 BRIEF SUMMARY (Telegram), etc.
        telegram_pattern = re.compile(
            r'^#+\s*\S?\s*.*?(?:telegram[_\s]?summary|тг[_\s]?сводка|телеграм[_\s]?сводка).*$',
            re.IGNORECASE | re.MULTILINE,
        )
        brief_pattern = re.compile(
            r'^#+\s*\S?\s*.*?(?:brief[_\s]?summary|краткая[_\s]?сводка).*$',
            re.IGNORECASE | re.MULTILINE,
        )
        detailed_pattern = re.compile(
            r'^#+\s*\S?\s*.*?(?:detailed[_\s]?report|подробный[_\s]?отч[её]т).*$',
            re.IGNORECASE | re.MULTILINE,
        )

        # Find all section matches and sort by position
        matches = []
        for name, pattern in [
            ("telegram_summary", telegram_pattern),
            ("brief_summary", brief_pattern),
            ("detailed_report", detailed_pattern),
        ]:
            m = pattern.search(content)
            if m:
                matches.append((name, m.start(), m.end()))

        if matches:
            matches.sort(key=lambda x: x[1])
            sections = {}
            for i, (name, _start, end) in enumerate(matches):
                next_start = matches[i + 1][1] if i + 1 < len(matches) else len(content)
                sections[name] = content[end:next_start].strip()

            telegram = sections.get("telegram_summary", "")
            brief = sections.get("brief_summary", "")
            detailed = sections.get("detailed_report", "")
        else:
            # No markers — use first ~4000 chars as brief
            brief = content[:4000].strip()
            detailed = content

        return {
            "telegram_summary": telegram,
            "brief_summary": brief or content[:4000],
            "detailed_report": detailed or content,
        }

    async def _synthesize(
        self, task: str, chain_history: list[AgentStep],
    ) -> dict:
        """Synthesize final answer from chain results."""

        # If only one step and it's reporter or marketer — use its output directly
        if len(chain_history) == 1 and chain_history[0].agent in ("reporter", "marketer", "funnel"):
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
                "telegram_summary": "",
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

    def _extract_structured_data(self, result) -> dict:
        """Extract structured data from agent's tool call history."""
        collected = {}
        for step in result.steps:
            source_tag = SOURCE_MAP.get(step.tool_name)
            if not source_tag or not step.tool_result:
                continue
            try:
                parsed = json.loads(step.tool_result)
                if isinstance(parsed, dict):
                    parsed["_source"] = source_tag
                    if source_tag in collected:
                        if not isinstance(collected[source_tag], list):
                            collected[source_tag] = [collected[source_tag]]
                        collected[source_tag].append(parsed)
                    else:
                        collected[source_tag] = parsed
            except (json.JSONDecodeError, TypeError):
                continue
        return collected

    # ── Advisor chain ─────────────────────────────────────────────

    def _load_kb_patterns(self) -> list[dict]:
        """Load KB patterns from Supabase. Returns [] on failure."""
        try:
            from shared.signals.kb_patterns import load_kb_patterns
            return load_kb_patterns(verified_only=True)
        except Exception as e:
            logger.warning(f"Failed to load KB patterns: {e}")
            return []

    async def _run_signal_detection(self, structured_data: dict) -> tuple[list, list]:
        """Run Signal Detector on structured data. Pure Python, no LLM.

        Returns:
            (signals_as_dicts, kb_patterns) — signals and loaded KB patterns
            for downstream use (Validator).
        """
        try:
            kb_patterns = self._load_kb_patterns()
            all_signals = []
            for source_tag, source_data in structured_data.items():
                relevant_kb = [p for p in kb_patterns if p.get("source_tag") == source_tag]
                if isinstance(source_data, list):
                    for item in source_data:
                        all_signals.extend(detect_signals(data=item, kb_patterns=relevant_kb))
                else:
                    all_signals.extend(detect_signals(data=source_data, kb_patterns=relevant_kb))
            return [vars(s) for s in all_signals], kb_patterns
        except Exception as e:
            logger.warning(f"Signal detection failed: {e}")
            return [], []

    async def _run_advisor_chain(
        self,
        structured_data: dict,
        report_type: str,
        chain_history: list,
    ) -> dict:
        """
        Run advisor chain: Signal Detection -> Advisor -> Validator.
        Returns validated recommendations or empty dict on failure.
        """
        advisor_start = time.time()
        result = {"recommendations": [], "signals": []}
        attempts = 1
        new_patterns = []

        try:
            # Step 1: Signal detection (pure Python, no LLM)
            signals, kb_patterns = await self._run_signal_detection(structured_data)
            if not signals:
                logger.info("Advisor chain: no signals detected, skipping")
                return result

            logger.info(f"Advisor chain: {len(signals)} signals detected")

            # Step 2: Advisor — generate recommendations
            advisor = self.agents.get("advisor")
            if not advisor:
                logger.warning("Advisor agent not registered, skipping chain")
                result = {"recommendations": [], "signals": signals}
                return result

            advisor_instruction = (
                f"Сформируй рекомендации для {report_type} отчёта.\n\n"
                f"signals = {json.dumps(signals, ensure_ascii=False, default=str)}\n\n"
                f"structured_data = {json.dumps(structured_data, ensure_ascii=False, default=str)}\n\n"
                f"report_type = \"{report_type}\""
            )

            advisor_result = await advisor.analyze(
                instruction=advisor_instruction,
                context="",
            )

            # Parse advisor output
            try:
                advisor_output = json.loads(advisor_result.content)
                recommendations = advisor_output.get("recommendations", [])
            except (json.JSONDecodeError, AttributeError):
                logger.warning("Advisor output is not valid JSON, skipping validation")
                result = {"recommendations": [], "signals": signals, "raw_advisor": advisor_result.content}
                return result

            # Extract and save proposed patterns (Phase 3: Self-Learning)
            new_patterns = advisor_output.get("new_patterns", [])
            if new_patterns:
                try:
                    from shared.signals.kb_patterns import save_proposed_patterns
                    saved = save_proposed_patterns(new_patterns)
                    logger.info(f"Advisor proposed {len(new_patterns)} patterns, {saved} saved")
                except Exception as e:
                    logger.warning(f"Failed to save proposed patterns: {e}")

            if not recommendations:
                result = {"recommendations": [], "signals": signals}
                return result

            # Step 3: Validator — verify recommendations
            validator = self.agents.get("validator")
            if not validator:
                logger.warning("Validator agent not registered, returning unverified")
                for r in recommendations:
                    r["verified"] = False
                result = {"recommendations": recommendations, "signals": signals}
                return result

            validator_instruction = (
                f"Проверь рекомендации от Advisor.\n\n"
                f"recommendations = {json.dumps(recommendations, ensure_ascii=False, default=str)}\n\n"
                f"signals = {json.dumps(signals, ensure_ascii=False, default=str)}\n\n"
                f"structured_data = {json.dumps(structured_data, ensure_ascii=False, default=str)}\n\n"
                f"kb_patterns = {json.dumps(kb_patterns, ensure_ascii=False, default=str)}"
            )

            validator_result = await validator.analyze(
                instruction=validator_instruction,
                context="",
            )

            try:
                verdict = json.loads(validator_result.content)
            except (json.JSONDecodeError, AttributeError):
                logger.warning("Validator output is not valid JSON, returning unverified")
                for r in recommendations:
                    r["verified"] = False
                result = {"recommendations": recommendations, "signals": signals}
                return result

            if verdict.get("verdict") == "pass":
                for r in recommendations:
                    r["verified"] = True
                result = {"recommendations": recommendations, "signals": signals, "verdict": verdict}
                return result

            # Step 4: Retry once — send validator feedback to advisor
            logger.info(f"Validator: FAIL — {verdict.get('issues', [])}")
            attempts = 2
            retry_instruction = (
                f"Валидатор отклонил рекомендации. Исправь и повтори.\n\n"
                f"Проблемы: {json.dumps(verdict.get('issues', []), ensure_ascii=False)}\n\n"
                f"Оригинальные рекомендации: {json.dumps(recommendations, ensure_ascii=False, default=str)}\n\n"
                f"signals = {json.dumps(signals, ensure_ascii=False, default=str)}\n\n"
                f"report_type = \"{report_type}\""
            )

            retry_result = await advisor.analyze(instruction=retry_instruction, context="")
            try:
                retry_output = json.loads(retry_result.content)
                retry_recs = retry_output.get("recommendations", [])
            except (json.JSONDecodeError, AttributeError):
                for r in recommendations:
                    r["verified"] = False
                result = {"recommendations": recommendations, "signals": signals}
                return result

            # Re-validate
            revalidate_instruction = (
                f"Проверь исправленные рекомендации.\n\n"
                f"recommendations = {json.dumps(retry_recs, ensure_ascii=False, default=str)}\n\n"
                f"signals = {json.dumps(signals, ensure_ascii=False, default=str)}\n\n"
                f"structured_data = {json.dumps(structured_data, ensure_ascii=False, default=str)}\n\n"
                f"kb_patterns = {json.dumps(kb_patterns, ensure_ascii=False, default=str)}"
            )

            rev2 = await validator.analyze(instruction=revalidate_instruction, context="")
            try:
                verdict2 = json.loads(rev2.content)
            except (json.JSONDecodeError, AttributeError):
                verdict2 = {"verdict": "fail"}

            if verdict2.get("verdict") == "pass":
                for r in retry_recs:
                    r["verified"] = True
                result = {"recommendations": retry_recs, "signals": signals, "verdict": verdict2}
            else:
                # Final fallback — include unverified
                logger.warning("Advisor chain: validator failed twice, returning unverified")
                for r in retry_recs:
                    r["verified"] = False
                result = {"recommendations": retry_recs, "signals": signals, "verdict": verdict2}

            return result

        except Exception as e:
            logger.warning(f"Advisor chain unexpected error: {e}")
            if not result.get("signals"):
                result = {"recommendations": [], "signals": []}
            return result

        finally:
            duration_ms = int((time.time() - advisor_start) * 1000)
            result["attempts"] = attempts
            if new_patterns:
                result["new_patterns"] = new_patterns
            self._log_recommendation(result, report_type, duration_ms)

    def _log_recommendation(self, result: dict, report_type: str, duration_ms: int):
        """Log advisor chain result to local SQLite via StateStore."""
        try:
            from agents.oleg.storage.state_store import StateStore
            store = StateStore("agents/oleg/data/oleg.db")
            store.init_db()
            store.log_recommendation(
                report_date=date.today().isoformat(),
                report_type=report_type,
                context="financial",
                signals_count=len(result.get("signals", [])),
                recommendations_count=len(result.get("recommendations", [])),
                validation_verdict=result.get("verdict", {}).get("verdict", "skipped"),
                validation_attempts=result.get("attempts", 1),
                signals=result.get("signals", []),
                recommendations=result.get("recommendations", []),
                validation_details=result.get("verdict", {}),
                new_patterns=result.get("new_patterns", []),
                advisor_cost_usd=0.0,
                validator_cost_usd=0.0,
                total_duration_ms=duration_ms,
            )
        except Exception as e:
            logger.warning(f"Failed to log recommendation: {e}")

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
