import os
import datetime
import pytest
import numpy as np
import polars as pl
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import load_config
from src.data.database import Base, get_db, MarketData, PortfolioState
from src.features.calculations import FeatureCalculator
from src.simulation.backtester import Backtester
from src.simulation.walk_forward import MonteCarloSimulator
from src.models.train import EnsembleModel, ModelTrainer
from src.risk.evaluator import RiskEvaluator
from src.agents.ceo import CEOAgent
from src.api.server import app

# 1. Test Config Loading
def test_config_load():
    cfg = load_config()
    assert cfg.system.environment == "development"
    assert cfg.broker.symbol == "XAUUSD"
    assert cfg.risk.max_daily_loss_pct > 0.0

# 2. Test Feature Calculator
def test_feature_calculations():
    # Construct dummy candle series
    dates = [datetime.datetime(2026, 7, 1) + datetime.timedelta(minutes=i) for i in range(100)]
    prices = [2300.0 + np.sin(i / 5.0) * 10.0 for i in range(100)]
    
    df = pl.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
        "volume": [100.0] * 100,
        "bid": [p - 0.1 for p in prices],
        "ask": [p + 0.1 for p in prices]
    })
    
    fe_df = FeatureCalculator.compute_all_features(df)
    
    assert "close_sma_10" in fe_df.columns
    assert "close_rsi_14" in fe_df.columns
    assert "atr_14" in fe_df.columns
    assert "is_london_session" in fe_df.columns
    assert fe_df.height == 100

# 3. Test Backtester Engine
def test_backtester():
    dates = [datetime.datetime(2026, 7, 1) + datetime.timedelta(minutes=i) for i in range(100)]
    prices = [2300.0 + i * 0.2 for i in range(100)] # steady uptrend
    
    df = pl.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
        "volume": [100.0] * 100,
        "atr_14": [1.5] * 100
    })
    
    # Signal: buy at idx 10, hold, flatten at idx 90
    signals = [0] * 100
    for idx in range(10, 90):
        signals[idx] = 1
        
    engine = Backtester(initial_capital=100000.0)
    results = engine.run(df, signals)
    
    assert results["total_trades"] > 0
    assert results["final_capital"] > 100000.0 # profit since it was a steady uptrend
    assert results["win_rate"] == 1.0

# 4. Test Monte Carlo Simulator
def test_monte_carlo():
    returns = np.array([0.002, -0.001, 0.003, -0.002, 0.005])
    sim = MonteCarloSimulator.simulate_paths(returns, num_simulations=50, path_length=20)
    
    assert "risk_of_ruin_pct" in sim
    assert "drawdown_95_var" in sim
    assert len(sim["simulated_curves"]) == 10

# 5. Database Integration & API Server Tests
# Setup isolated SQLite in-memory DB for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    
    # Seed initial portfolio state
    initial = PortfolioState(
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        balance=100000.0,
        equity=100000.0,
        margin_used=0.0,
        free_margin=100000.0,
        leverage=1.0,
        var_95=500.0,
        drawdown=0.0
    )
    db.add(initial)
    db.commit()
    
    yield db
    Base.metadata.drop_all(bind=test_engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def test_api_endpoints(setup_db):
    # Test public info dashboard fetches
    response = client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 100000.0
    
    response = client.get("/api/v1/portfolio/positions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    # Test login authentication fail
    response = client.post("/api/v1/auth/login", data={"username": "admin", "password": "wrongpassword"})
    assert response.status_code == 401

    # Test login success - Admin
    response = client.post("/api/v1/auth/login", data={"username": "admin", "password": "admin_password"})
    assert response.status_code == 200
    admin_token = response.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Test login success - Viewer
    response = client.post("/api/v1/auth/login", data={"username": "viewer", "password": "viewer_password"})
    assert response.status_code == 200
    viewer_token = response.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # Test Viewer block on emergency shutdown (Should be 403 Forbidden)
    response = client.post("/api/v1/system/emergency-shutdown", headers=viewer_headers)
    assert response.status_code == 403

    # Test Admin success on emergency shutdown (Should be 200)
    response = client.post("/api/v1/system/emergency-shutdown", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "SHUTDOWN_COMPLETE"

    # Test Researcher login
    response = client.post("/api/v1/auth/login", data={"username": "researcher", "password": "researcher_password"})
    assert response.status_code == 200
    researcher_token = response.json()["access_token"]
    researcher_headers = {"Authorization": f"Bearer {researcher_token}"}

    # Test backtester API endpoint (Researcher should succeed)
    response = client.post("/api/v1/research/backtest", json={"start_days_ago": 30, "slippage_pips": 1.0}, headers=researcher_headers)
    assert response.status_code == 200
    assert "final_capital" in response.json()

