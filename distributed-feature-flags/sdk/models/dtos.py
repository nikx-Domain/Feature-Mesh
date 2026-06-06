from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class SDKTargetingRule:
    id: str
    attribute: str
    operator: str
    value: Any
    serve_variation_id: str
    priority: int

@dataclass
class SDKRolloutRule:
    id: str
    percentage: int
    serve_variation_id: str

@dataclass
class SDKFeatureFlagEnvironment:
    is_enabled: bool
    default_serve_variation_id: Optional[str] = None
    off_variation_id: Optional[str] = None
    targeting_rules: List[SDKTargetingRule] = field(default_factory=list)
    rollout_rules: List[SDKRolloutRule] = field(default_factory=list)

@dataclass
class SDKFlagVariation:
    id: str
    name: str
    value: Any

@dataclass
class SDKFeatureFlag:
    id: str
    key: str
    type: str
    version: int
    environment: SDKFeatureFlagEnvironment
    variations: List[SDKFlagVariation]

@dataclass
class SDKSnapshot:
    environment_id: str
    flags: Dict[str, SDKFeatureFlag]

def parse_snapshot(data: dict) -> SDKSnapshot:
    flags = {}
    for flag_key, flag_data in data.get("flags", {}).items():
        env_data = flag_data.get("environment", {})
        
        targeting_rules = [
            SDKTargetingRule(**rule) for rule in env_data.get("targeting_rules", [])
        ]
        rollout_rules = [
            SDKRolloutRule(**rule) for rule in env_data.get("rollout_rules", [])
        ]
        
        env = SDKFeatureFlagEnvironment(
            is_enabled=env_data.get("is_enabled", False),
            default_serve_variation_id=env_data.get("default_serve_variation_id"),
            off_variation_id=env_data.get("off_variation_id"),
            targeting_rules=targeting_rules,
            rollout_rules=rollout_rules
        )
        
        variations = [
            SDKFlagVariation(**var) for var in flag_data.get("variations", [])
        ]
        
        flag = SDKFeatureFlag(
            id=flag_data["id"],
            key=flag_data["key"],
            type=flag_data["type"],
            version=flag_data["version"],
            environment=env,
            variations=variations
        )
        flags[flag_key] = flag
        
    return SDKSnapshot(
        environment_id=data.get("environment_id", ""),
        flags=flags
    )
