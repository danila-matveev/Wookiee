"""Custom field value validation and management."""
from __future__ import annotations
from datetime import date
from typing import Any, Optional

MAX_CUSTOM_FIELDS = 50


class FieldService:
    """Stateless helpers for custom field operations."""

    @staticmethod
    def validate_value(field_type: str, value: Any, config: Optional[dict] = None) -> Any:
        """Validate and coerce a custom field value based on its type."""
        if value is None:
            return None
        config = config or {}

        if field_type == "text":
            return str(value)
        if field_type == "number":
            try:
                return float(value) if "." in str(value) else int(value)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert {value!r} to number")
        if field_type == "checkbox":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        if field_type == "select":
            options = config.get("options", [])
            if options and value not in options:
                raise ValueError(f"{value!r} not in allowed options: {options}")
            return value
        if field_type == "multi_select":
            if not isinstance(value, list):
                raise ValueError("multi_select value must be a list")
            options = config.get("options", [])
            if options:
                invalid = [v for v in value if v not in options]
                if invalid:
                    raise ValueError(f"{invalid} not in allowed options: {options}")
            return value
        if field_type == "date":
            if isinstance(value, date):
                return value.isoformat()
            try:
                date.fromisoformat(str(value))
                return str(value)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid date: {value!r}")
        if field_type in ("url", "file"):
            return str(value)
        # relation, formula, rollup — pass through
        return value

    @staticmethod
    def merge_custom_fields(existing: dict, updates: dict) -> dict:
        """Merge updates into existing custom_fields. None values remove keys."""
        result = dict(existing)
        for k, v in updates.items():
            if v is None:
                result.pop(k, None)
            else:
                result[k] = v
        if len(result) > MAX_CUSTOM_FIELDS:
            raise ValueError(f"Maximum {MAX_CUSTOM_FIELDS} custom fields per entity")
        return result
