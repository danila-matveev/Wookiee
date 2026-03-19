"""
Funnel Agent tools — delegates to services/funnel_tools.py.

Tool definitions and handlers for funnel analysis (Макар).
All SQL queries delegate to shared/data_layer.py.
"""
from agents.oleg.services.funnel_tools import (
    FUNNEL_TOOL_DEFINITIONS,
    execute_funnel_tool,
)

__all__ = ["FUNNEL_TOOL_DEFINITIONS", "execute_funnel_tool"]
