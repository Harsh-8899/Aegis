import os
import yaml
from pathlib import Path
from pydantic import BaseModel, Field

# Load .env file manually into os.environ if it exists
env_path = Path(__file__).resolve().parent.parent / ".env"
if not env_path.exists():
    env_path = Path("./.env")
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()


class DatabaseConfig(BaseModel):
    url: str
    pool_size: int = 10
    max_overflow: int = 20

class RedisConfig(BaseModel):
    host: str
    port: int
    db: int = 0

class BrokerConfig(BaseModel):
    provider: str
    api_key: str
    api_secret: str
    base_url: str
    symbol: str = "XAUUSD"
    min_lot_size: float = 0.01
    max_lot_size: float = 5.0
    leverage: float = 10.0

class RiskConfig(BaseModel):
    max_daily_loss_pct: float = 0.02
    max_weekly_loss_pct: float = 0.05
    max_monthly_loss_pct: float = 0.10
    max_position_exposure_pct: float = 0.15
    max_drawdown_pct: float = 0.08
    var_95_limit: float = 5000.0
    slippage_buffer_pips: float = 3.0
    emergency_shutdown_key: str

class PortfolioConfig(BaseModel):
    allocation_method: str = "risk_parity"
    rebalance_frequency: str = "daily"
    strategies: dict[str, float]

class MLRegistryConfig(BaseModel):
    mlflow_tracking_uri: str
    model_dir: str
    drift_threshold_ks: float = 0.05
    min_precision: float = 0.55

class SystemConfig(BaseModel):
    environment: str = "development"
    log_level: str = "INFO"
    shutdown_on_risk_breach: bool = True

class GoldAPIConfig(BaseModel):
    key: str = "goldapi-065303dbfd3379c140c026c78e27b057-io"

class AppConfig(BaseModel):
    system: SystemConfig
    database: DatabaseConfig
    redis: RedisConfig
    broker: BrokerConfig
    risk: RiskConfig
    portfolio: PortfolioConfig
    ml_registry: MLRegistryConfig
    goldapi: GoldAPIConfig = GoldAPIConfig()

_config: AppConfig | None = None

def get_config_path() -> Path:
    env = os.getenv("ENV", "development")
    root_dir = Path(__file__).resolve().parent.parent
    config_file = root_dir / "config" / f"{env}.yaml"
    if not config_file.exists():
        # Fallback if executing from src/ or similar context
        config_file = Path(f"./config/{env}.yaml")
    return config_file

def load_config() -> AppConfig:
    global _config
    if _config is not None:
        return _config
    
    config_path = get_config_path()
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
        
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
        
    _config = AppConfig(**data)
    return _config
