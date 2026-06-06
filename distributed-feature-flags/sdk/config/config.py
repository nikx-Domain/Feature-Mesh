from dataclasses import dataclass

@dataclass
class SDKConfig:
    api_key: str
    base_url: str = "http://localhost:8000"
    timeout: float = 5.0
    refresh_interval: float = 30.0
    offline_mode: bool = False
    bootstrap_timeout: float = 5.0
