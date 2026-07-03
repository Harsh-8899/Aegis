import time
import datetime
import pytest
from src.features.live_engine import LiveFeatureEngine

def test_live_feature_calculations():
    engine = LiveFeatureEngine(window_size=100)
    
    # Send 10 price ticks
    base_time = datetime.datetime.now(datetime.timezone.utc)
    for i in range(25):
        tick = {
            "timestamp": (base_time + datetime.timedelta(seconds=i)).isoformat(),
            "symbol": "XAUUSD",
            "price": 2300.0 + i * 0.1,  # ascending trend
            "bid": 2299.9 + i * 0.1,
            "ask": 2300.1 + i * 0.1,
            "spread": 0.2,
            "volume": 10.0
        }
        start_t = time.perf_counter()
        features = engine.update(tick)
        duration = time.perf_counter() - start_t
        
        # Verify latency constraint (<100ms, usually <1ms in local runs)
        assert duration < 0.100
        
    # Verify values calculated
    assert features["price"] == 2302.4
    assert features["return_1s"] > 0
    assert features["return_5s"] > 0
    assert features["momentum"] > 0
    assert features["candle_direction"] == 1.0
    assert "macd" in features
    assert "rsi_14" in features
    assert "z_score" in features
    assert "market_regime" in features
