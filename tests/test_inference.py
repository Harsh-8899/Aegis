import time
import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.data.database import Base, PortfolioState
from src.features.live_engine import LiveFeatureEngine
from src.models.inference import QuantIntelligenceEngine
from src.strategies.fusion import SignalFusionEngine
from src.risk.gate import RiskGate

# Isolated DB setup for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_inference.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Setup initial portfolio state
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
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_intelligence_and_fusion_flow(setup_test_db):
    db = setup_test_db
    
    # 1. Warm up features
    feature_engine = LiveFeatureEngine()
    base_time = datetime.datetime.now(datetime.timezone.utc)
    
    for i in range(40):
        tick = {
            "timestamp": (base_time + datetime.timedelta(seconds=i)).isoformat(),
            "symbol": "XAUUSD",
            "price": 2300.0 + i * 0.2,
            "bid": 2300.0 + i * 0.2 - 0.09,
            "ask": 2300.0 + i * 0.2 + 0.09,
            "spread": 0.18,
            "volume": 20.0
        }
        features = feature_engine.update(tick)

    # 2. Run Inference
    quant_engine = QuantIntelligenceEngine(db)
    start_t = time.perf_counter()
    model_outputs = quant_engine.run_all_models(features, feature_engine.prices)
    duration = time.perf_counter() - start_t
    
    # Verify model inference latency constraint (<200ms)
    assert duration < 0.200
    
    assert "kalman" in model_outputs
    assert "hmm" in model_outputs
    assert "garch" in model_outputs
    assert "z_score_mr" in model_outputs
    
    # 3. Test Signal Fusion
    fusion_engine = SignalFusionEngine()
    fused_sig = fusion_engine.fuse_signals(model_outputs, tick["price"], features["atr_14"])
    
    assert "signal" in fused_sig
    assert "confidence" in fused_sig
    assert "risk_score" in fused_sig
    assert "market_regime" in fused_sig
    assert len(fused_sig["suggested_sl_range"]) == 2
    
    # 4. Test Risk Gate
    risk_gate = RiskGate(db)
    # Check normal trade approval
    approved, reason = risk_gate.verify_trade(
        direction="BUY", volume=0.5, price=tick["price"],
        spread=tick["spread"], expected_vol=0.0005, risk_score=15.0
    )
    assert approved is True
    
    # Check veto under wide spread
    approved_wide, reason_wide = risk_gate.verify_trade(
        direction="BUY", volume=0.5, price=tick["price"],
        spread=0.45, expected_vol=0.0005, risk_score=15.0
    )
    assert approved_wide is False
    assert "SPREAD_WIDENING" in reason_wide
