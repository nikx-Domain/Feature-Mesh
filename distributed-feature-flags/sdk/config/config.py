from dataclasses import dataclass
from typing import Optional, Protocol, Dict, Any

class MetricsReporter(Protocol):
    def increment(self, metric_name: str, labels: Optional[Dict[str, str]] = None) -> None:
        ...

@dataclass
class SDKConfig:
    api_key: str
    base_url: str = "http://localhost:8000"
    timeout: float = 5.0
    refresh_interval: float = 30.0
    offline_mode: bool = False
    bootstrap_timeout: float = 5.0
    metrics_reporter: Optional[MetricsReporter] = None
