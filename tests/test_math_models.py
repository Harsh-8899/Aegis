import numpy as np
import pytest
from src.models.math_models import (
    KalmanFilterPriceTracker, GARCHVolatilityForecaster, 
    HiddenMarkovModel, AutoRegressiveModel
)

# 1. Test Kalman Filter Tracker
def test_kalman_filter_price_tracker():
    tracker = KalmanFilterPriceTracker(process_noise=0.1, measurement_noise=0.1)
    
    # Run filter on a linear step trend: 10, 11, 12, 13, 14
    prices = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
    filtered = tracker.run_series(prices)
    
    assert len(filtered) == 5
    # The filter should smooth out steps and move towards the true final value
    assert filtered[-1] > 12.0
    assert filtered[-1] <= 14.0

# 2. Test GARCH Volatility Forecaster
def test_garch_volatility_forecaster():
    forecaster = GARCHVolatilityForecaster()
    
    # Generate mock heteroskedastic returns: high vol periods and low vol periods
    np.random.seed(42)
    low_vol = np.random.normal(0, 0.001, 30)
    high_vol = np.random.normal(0, 0.005, 30)
    returns = np.concatenate([low_vol, high_vol])
    
    success = forecaster.fit(returns)
    assert success is True
    assert forecaster.alpha >= 0.0
    assert forecaster.beta >= 0.0
    
    next_var = forecaster.forecast_next_variance(returns)
    assert next_var > 0.0

# 3. Test Hidden Markov Model
def test_hidden_markov_model_viterbi():
    hmm = HiddenMarkovModel()
    
    # Generate mock returns
    np.random.seed(42)
    low_vol = np.random.normal(0, 0.0001, 40)
    high_vol = np.random.normal(0, 0.002, 40)
    returns = np.concatenate([low_vol, high_vol])
    
    states = hmm.predict_regime_states(returns)
    
    assert len(states) == 80
    # State values must be strictly 0 or 1
    assert set(states).issubset({0, 1})
    # High vol returns should tend to be classified as state 1
    assert np.mean(states[40:]) >= np.mean(states[:40])

# 4. Test AutoRegressive Model
def test_autoregressive_model():
    model = AutoRegressiveModel(lags=2)
    
    # Construct lag-predictable series: r_t = 0.5 * r_t-1 - 0.2 * r_t-2
    np.random.seed(42)
    returns = np.zeros(50)
    for t in range(2, 50):
        returns[t] = 0.5 * returns[t-1] - 0.2 * returns[t-2] + np.random.normal(0, 0.0001)
        
    success = model.fit(returns)
    assert success is True
    assert len(model.coefficients) == 2
    
    # Verify coefficients estimated are in the correct stability bounds
    assert -1.0 < model.coefficients[0] < 1.0
    
    next_return = model.predict_next_return(returns)
    assert isinstance(next_return, float)
