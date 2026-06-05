import re
from typing import Any

from app.domain.entities import TargetingOperator


def _coerce_to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _coerce_to_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def evaluate_operator(context_value: Any, operator: TargetingOperator, rule_value: Any) -> bool:
    """Evaluates a targeting rule operator securely."""

    # Missing attribute in context
    if context_value is None and operator not in (
        TargetingOperator.NOT_EQUALS,
        TargetingOperator.NOT_IN,
        TargetingOperator.NOT_CONTAINS,
    ):
        return False

    if operator == TargetingOperator.EQUALS:
        return context_value == rule_value

    if operator == TargetingOperator.NOT_EQUALS:
        return context_value != rule_value

    if operator == TargetingOperator.IN:
        return context_value in _coerce_to_list(rule_value)

    if operator == TargetingOperator.NOT_IN:
        return context_value not in _coerce_to_list(rule_value)

    if operator == TargetingOperator.CONTAINS:
        return _coerce_to_str(rule_value) in _coerce_to_str(context_value)

    if operator == TargetingOperator.NOT_CONTAINS:
        return _coerce_to_str(rule_value) not in _coerce_to_str(context_value)

    if operator == TargetingOperator.MATCHES_REGEX:
        try:
            pattern = re.compile(_coerce_to_str(rule_value))
            return bool(pattern.search(_coerce_to_str(context_value)))
        except re.error:
            return False

    if operator in (TargetingOperator.GREATER_THAN, TargetingOperator.LESS_THAN):
        # We only support comparing numbers or comparing strings.
        if isinstance(context_value, (int, float)) and isinstance(rule_value, (int, float)):
            if operator == TargetingOperator.GREATER_THAN:
                return context_value > rule_value
            return context_value < rule_value

        if isinstance(context_value, str) and isinstance(rule_value, str):
            if operator == TargetingOperator.GREATER_THAN:
                return context_value > rule_value
            return context_value < rule_value

        return False

    return False
