import datetime
import enum
from typing import Generator
from sqlalchemy import (
    create_engine, Column, Integer, Numeric, String, DateTime, Boolean, 
    Enum, ForeignKey, Text, UniqueConstraint, JSON, Uuid
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import uuid

from src.config import load_config

# Load DB Configurations
cfg = load_config()

if cfg.database.url.startswith("sqlite"):
    db_url = cfg.database.url
    # Resolve relative paths like sqlite:///./quant_trading.db to project root
    if "sqlite:///./" in db_url:
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent.parent
        db_file = db_url.replace("sqlite:///./", "")
        db_url = f"sqlite:///{project_root}/{db_file}"
    elif "sqlite:///" in db_url and not db_url.startswith("sqlite:////"):
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent.parent
        db_file = db_url.replace("sqlite:///", "")
        db_url = f"sqlite:///{project_root}/{db_file}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        cfg.database.url,
        pool_size=cfg.database.pool_size,
        max_overflow=cfg.database.max_overflow
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums
class TradeDirection(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

# Models
class MarketData(Base):
    __tablename__ = "market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    symbol = Column(String(12), nullable=False, default="XAUUSD")
    timeframe = Column(String(4), nullable=False) # '1m', '5m', '1h', '1d', 'tick'
    open = Column(Numeric(10, 4))
    high = Column(Numeric(10, 4))
    low = Column(Numeric(10, 4))
    close = Column(Numeric(10, 4))
    volume = Column(Numeric(12, 4))
    bid = Column(Numeric(10, 4))
    ask = Column(Numeric(10, 4))

    __table_args__ = (
        UniqueConstraint('symbol', 'timeframe', 'timestamp', name='uq_symbol_tf_ts'),
    )

class MacroEvent(Base):
    __tablename__ = "macro_events"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    event_name = Column(String(100), nullable=False)
    country = Column(String(10), nullable=False)
    actual = Column(Numeric(10, 4))
    forecast = Column(Numeric(10, 4))
    previous = Column(Numeric(10, 4))
    importance = Column(String(10)) # 'HIGH', 'MEDIUM', 'LOW'

class NewsSentiment(Base):
    __tablename__ = "news_sentiment"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    sentiment_score = Column(Numeric(4, 3), nullable=False)
    sentiment_embedding = Column(JSON)

class Strategy(Base):
    __tablename__ = "strategies"
    
    strategy_id = Column(String(50), primary_key=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    config = Column(JSON, nullable=False)

class ModelRegistry(Base):
    __tablename__ = "model_registry"
    
    model_version = Column(String(50), primary_key=True)
    model_type = Column(String(50), nullable=False)
    mlflow_run_id = Column(String(100))
    metrics = Column(JSON, nullable=False)
    filepath = Column(Text, nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

class PortfolioState(Base):
    __tablename__ = "portfolio_state"
    
    timestamp = Column(DateTime(timezone=True), primary_key=True, index=True)
    balance = Column(Numeric(15, 2), nullable=False)
    equity = Column(Numeric(15, 2), nullable=False)
    margin_used = Column(Numeric(15, 2), nullable=False)
    free_margin = Column(Numeric(15, 2), nullable=False)
    leverage = Column(Numeric(5, 2), nullable=False)
    var_95 = Column(Numeric(10, 2), nullable=False)
    drawdown = Column(Numeric(5, 4), nullable=False)

class Order(Base):
    __tablename__ = "orders"
    
    order_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id = Column(String(50), ForeignKey("strategies.strategy_id"))
    direction = Column(Enum(TradeDirection), nullable=False)
    volume = Column(Numeric(10, 2), nullable=False)
    limit_price = Column(Numeric(10, 4))
    stop_price = Column(Numeric(10, 4))
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    created_at = Column(DateTime(timezone=True), nullable=False)
    filled_at = Column(DateTime(timezone=True))
    fill_price = Column(Numeric(10, 4))
    slippage = Column(Numeric(8, 4))
    latency_ms = Column(Integer)

class Position(Base):
    __tablename__ = "positions"
    
    position_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id = Column(Uuid, ForeignKey("orders.order_id"))
    direction = Column(Enum(TradeDirection), nullable=False)
    entry_price = Column(Numeric(10, 4), nullable=False)
    volume = Column(Numeric(10, 2), nullable=False)
    stop_loss = Column(Numeric(10, 4), nullable=False)
    take_profit = Column(Numeric(10, 4), nullable=False)
    unrealized_pnl = Column(Numeric(12, 4), default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True))
    exit_price = Column(Numeric(10, 4))
    realized_pnl = Column(Numeric(12, 4))

class SystemAlert(Base):
    __tablename__ = "system_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, index=True)
    agent_name = Column(String(50), nullable=False)
    severity = Column(String(10), nullable=False) # 'INFO', 'WARN', 'CRITICAL'
    message = Column(Text, nullable=False)

class UserFeedback(Base):
    __tablename__ = "user_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, index=True)
    username = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    category = Column(String(50), nullable=False)  # 'BUG', 'FEATURE', 'UIUX', 'GENERAL'
    rating = Column(Integer, nullable=False)       # 1 to 5
    comment = Column(Text, nullable=False)

# Session helper dependency
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper to create tables (useful for development before alembic setup)
def init_db():
    Base.metadata.create_all(bind=engine)
