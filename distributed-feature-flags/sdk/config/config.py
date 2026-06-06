from dataclasses import dataclass

@dataclass
class SDKConfig:
    api_key: str
    base_url: str = "http://localhost:8000"
    timeout: int = 5
    refresh_interval: int = 30
    bootstrap_mode: str = "fail_fast"  # 'fail_fast' or 'graceful'
    offline_mode: bool = False
