# agents/reporter/analyst/schemas.py
"""Pydantic models for LLM structured output."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MetricChange(BaseModel):
    metric: str = Field(description="Metric name: revenue, margin_pct, drr, orders, etc.")
    current: float
    previous: float
    delta_pct: float = Field(description="Percentage change from previous to current")
    direction: str = Field(description="up, down, or flat")


class RootCause(BaseModel):
    description: str = Field(description="Root cause explanation in Russian")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(description="Specific data points supporting this cause")
    recommendation: str = Field(description="Actionable recommendation in Russian")


class SectionInsight(BaseModel):
    section_id: int = Field(ge=0, le=12)
    title: str
    summary: str = Field(description="2-3 sentence summary in Russian")
    key_changes: list[MetricChange] = Field(default_factory=list)
    root_causes: list[RootCause] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)


class DiscoveredPattern(BaseModel):
    pattern: str = Field(description="Pattern description in Russian")
    evidence: str
    suggested_action: str
    confidence: float = Field(ge=0.0, le=1.0)


class ReportInsights(BaseModel):
    executive_summary: str = Field(description="3-5 sentences for Telegram, in Russian")
    sections: list[SectionInsight]
    discovered_patterns: list[DiscoveredPattern] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    analysis_notes: list[str] = Field(default_factory=list)
