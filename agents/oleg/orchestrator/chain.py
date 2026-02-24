"""
Chain — data structures for collaborative agent chains.
"""
from dataclasses import dataclass, field
from typing import List, Optional


MAX_CHAIN_STEPS = 5


@dataclass
class AgentStep:
    """One step in the orchestrator chain."""
    agent: str               # 'reporter', 'researcher', 'quality'
    instruction: str         # What the orchestrator asked
    result: str              # Agent's response
    cost_usd: float = 0.0
    duration_ms: int = 0
    iterations: int = 0      # ReAct loop iterations


@dataclass
class OrchestratorDecision:
    """What the orchestrator decides at each step."""
    done: bool = False           # True = synthesize final answer
    next_agent: str = ""         # Which agent to call next
    instruction: str = ""        # What to ask the agent
    reasoning: str = ""          # Why this decision


@dataclass
class ChainResult:
    """Final result of an orchestrator chain."""
    summary: str                     # Brief summary (BBCode for Telegram)
    detailed: Optional[str] = None   # Detailed report (Markdown for Notion)
    steps: List[AgentStep] = field(default_factory=list)
    total_steps: int = 0
    total_cost: float = 0.0
    total_duration_ms: int = 0
    task_type: str = ""
