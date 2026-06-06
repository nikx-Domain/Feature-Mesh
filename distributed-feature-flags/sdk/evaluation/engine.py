import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sdk.models.dtos import SDKFeatureFlag, SDKSnapshot

@dataclass
class EvaluationDecision:
    is_enabled: bool
    variation_id: Optional[str]
    variation_value: Any
    reason: str

class LocalEvaluationEngine:
    """
    Standalone local evaluation engine mirroring the backend's behavior.
    """
    
    @staticmethod
    def get_rollout_bucket(flag_key: str, context_key: str) -> int:
        hash_key = f"{flag_key}.{context_key}".encode()
        hash_hex = hashlib.sha256(hash_key).hexdigest()
        hash_int = int(hash_hex[:8], 16)
        return hash_int % 100000

    @staticmethod
    def evaluate_operator(context_value: Any, operator: str, rule_value: Any) -> bool:
        def _coerce_to_str(val: Any) -> str:
            return "" if val is None else str(val)

        def _coerce_to_list(val: Any) -> list:
            if isinstance(val, list): return val
            if val is None: return []
            return [val]

        if context_value is None and operator not in ("not_equals", "not_in", "not_contains"):
            return False

        if operator == "equals": return context_value == rule_value
        if operator == "not_equals": return context_value != rule_value
        if operator == "in": return context_value in _coerce_to_list(rule_value)
        if operator == "not_in": return context_value not in _coerce_to_list(rule_value)
        if operator == "contains": return _coerce_to_str(rule_value) in _coerce_to_str(context_value)
        if operator == "not_contains": return _coerce_to_str(rule_value) not in _coerce_to_str(context_value)
        if operator == "matches_regex":
            try:
                return bool(re.search(_coerce_to_str(rule_value), _coerce_to_str(context_value)))
            except re.error:
                return False
        
        if operator in ("greater_than", "less_than"):
            if isinstance(context_value, (int, float)) and isinstance(rule_value, (int, float)):
                return context_value > rule_value if operator == "greater_than" else context_value < rule_value
            if isinstance(context_value, str) and isinstance(rule_value, str):
                return context_value > rule_value if operator == "greater_than" else context_value < rule_value
                
        return False

    @classmethod
    def evaluate(cls, flag: SDKFeatureFlag, context: Dict[str, Any]) -> EvaluationDecision:
        variation_map = {v.id: v for v in flag.variations}
        env = flag.environment

        if not env.is_enabled:
            var_id = env.off_variation_id
            variation = variation_map.get(var_id) if var_id else None
            return EvaluationDecision(False, var_id, variation.value if variation else None, "DISABLED")

        # Targeting Rules
        sorted_rules = sorted(env.targeting_rules, key=lambda r: r.priority)
        for rule in sorted_rules:
            context_value = context.get(rule.attribute)
            if cls.evaluate_operator(context_value, rule.operator, rule.value):
                var_id = rule.serve_variation_id
                variation = variation_map.get(var_id)
                return EvaluationDecision(True, var_id, variation.value if variation else None, "TARGETING_MATCH")

        # Rollout Rules
        if env.rollout_rules:
            # Generate a context key if not provided (e.g. anonymous user)
            import uuid
            context_key = str(context.get("key", uuid.uuid4()))
            bucket = cls.get_rollout_bucket(flag.key, context_key)
            
            cumulative = 0
            sorted_rollout = sorted(env.rollout_rules, key=lambda r: r.id)
            for rule in sorted_rollout:
                threshold = cumulative + (rule.percentage * 1000)
                if bucket < threshold:
                    var_id = rule.serve_variation_id
                    variation = variation_map.get(var_id)
                    return EvaluationDecision(True, var_id, variation.value if variation else None, "ROLLOUT")
                cumulative = threshold

        # Default Serve
        var_id = env.default_serve_variation_id
        variation = variation_map.get(var_id) if var_id else None
        return EvaluationDecision(True, var_id, variation.value if variation else None, "DEFAULT")
