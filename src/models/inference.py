import logging
import numpy as np
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from src.models.math_models import (
    KalmanFilterPriceTracker,
    GARCHVolatilityForecaster,
    HiddenMarkovModel,
    AutoRegressiveModel,
    BayesianUncertaintyEstimator,
    MonteCarloPathSimulator,
    ZScoreMeanReversionModel,
    MomentumOscillatorModel,
    BreakoutProbabilityModel
)
from src.models.registry import ModelRegistryManager

logger = logging.getLogger("QuantIntelligence")

class QuantIntelligenceEngine:
    """
    Runs real-time quant model inferences every second.
    Executes Kalman Filter, GARCH, HMM, EWMA, Z-score, Momentum, Breakouts,
    and ML Ensemble inference.
    """
    def __init__(self, db: Session):
        self.db = db
        self.model_manager = ModelRegistryManager(db)
        
        # Trackers
        self.kalman = KalmanFilterPriceTracker(process_noise=0.02, measurement_noise=0.2)
        self.garch = GARCHVolatilityForecaster()
        self.hmm = HiddenMarkovModel()
        self.ar = AutoRegressiveModel()
        self.bayesian = BayesianUncertaintyEstimator()
        self.monte_carlo = MonteCarloPathSimulator()
        self.zscore_mr = ZScoreMeanReversionModel()
        self.momentum_osc = MomentumOscillatorModel()
        self.breakout = BreakoutProbabilityModel()
        
        # Volatility EWMA parameter
        self.ewma_decay = 0.94
        self.running_variance = 0.0001
        
        # Buffer of returns for GARCH and HMM
        self.returns_history: List[float] = []

    def run_all_models(self, live_features: Dict[str, Any], history_prices: List[float]) -> Dict[str, Dict[str, Any]]:
        """
        Runs all models on current live features and price history.
        Returns a dict mapping model_name -> model_outputs.
        """
        price = live_features["price"]
        spread = live_features["spread"]
        z_score = live_features["z_score"]
        momentum = live_features["momentum"]
        bb_pos = live_features["bb_position"]
        volatility = live_features["rolling_volatility"]
        
        # Update returns history
        if len(history_prices) > 1:
            rets = np.diff(np.log(history_prices))
            self.returns_history = list(rets[-100:]) # Limit to last 100 returns for speed
        else:
            self.returns_history = [0.0]

        rets_arr = np.array(self.returns_history)

        outputs = {}

        # 1. Kalman Filter
        outputs["kalman"] = self.kalman.predict(
            price=price, returns=rets_arr, z_score=z_score, momentum=momentum, bb_pos=bb_pos, volatility=volatility
        )

        # 2. EWMA Volatility
        if len(rets_arr) > 0:
            last_ret = rets_arr[-1]
            self.running_variance = self.ewma_decay * self.running_variance + (1 - self.ewma_decay) * (last_ret ** 2)
        ewma_vol = np.sqrt(self.running_variance)
        outputs["ewma_vol"] = {
            "buy_prob": 0.33, "sell_prob": 0.33, "hold_prob": 0.34,
            "confidence": 0.60,
            "expected_volatility": ewma_vol,
            "expected_move": 0.0,
            "current_regime": "HIGH_VOL" if ewma_vol > 0.001 else "LOW_VOL",
            "reason_codes": ["EWMA_VOL_UPDATED"]
        }

        # 3. GARCH Volatility Forecast
        outputs["garch"] = self.garch.predict(
            price=price, returns=rets_arr, z_score=z_score, momentum=momentum, bb_pos=bb_pos, volatility=volatility
        )

        # 4. Hidden Markov Model
        outputs["hmm"] = self.hmm.predict(
            price=price, returns=rets_arr, z_score=z_score, momentum=momentum, bb_pos=bb_pos, volatility=volatility
        )

        # 5. Z-Score Mean Reversion Detector
        outputs["z_score_mr"] = self.zscore_mr.predict(
            price=price, returns=rets_arr, z_score=z_score, momentum=momentum, bb_pos=bb_pos, volatility=volatility
        )

        # 6. Momentum/Trend Detector
        outputs["momentum"] = self.momentum_osc.predict(
            price=price, returns=rets_arr, z_score=z_score, momentum=momentum, bb_pos=bb_pos, volatility=volatility
        )

        # 7. Breakout Probability Model
        outputs["breakout"] = self.breakout.predict(
            price=price, returns=rets_arr, z_score=z_score, momentum=momentum, bb_pos=bb_pos, volatility=volatility
        )

        # 8. Bayesian Uncertainty Estimator
        outputs["bayesian"] = self.bayesian.predict(
            price=price, returns=rets_arr, z_score=z_score, momentum=momentum, bb_pos=bb_pos, volatility=volatility
        )

        # 9. Monte Carlo Path Simulator
        outputs["monte_carlo"] = self.monte_carlo.predict(
            price=price, returns=rets_arr, z_score=z_score, momentum=momentum, bb_pos=bb_pos, volatility=volatility
        )

        # 10. ML Ensemble Inference (RandomForest, ExtraTrees, GradientBoosting)
        ml_model = self.model_manager.get_active_model()
        ml_buy, ml_sell = 0.33, 0.33
        ml_conf = 0.50
        ml_regime = "ML_HOLD"
        ml_reasons = []
        
        if ml_model:
            try:
                # Align current live features with model's expected feature names
                X_vector = []
                for col in ml_model.feature_cols:
                    X_vector.append(live_features.get(col, 0.0))
                
                # Get probas
                probas = ml_model.predict_proba(np.array([X_vector]))[0]
                # probas contains probabilities for class labels: 0 (DOWN), 1 (FLAT), 2 (UP)
                ml_sell = float(probas[0])
                ml_hold = float(probas[1])
                ml_buy = float(probas[2])
                
                max_class = np.argmax(probas)
                ml_conf = float(probas[max_class])
                
                if max_class == 2:
                    ml_regime = "ML_BULLISH"
                    ml_reasons.append("ML_CONSENSUS_BUY")
                elif max_class == 0:
                    ml_regime = "ML_BEARISH"
                    ml_reasons.append("ML_CONSENSUS_SELL")
                else:
                    ml_regime = "ML_NEUTRAL"
                    ml_reasons.append("ML_CONSENSUS_HOLD")
            except Exception as e:
                logger.error(f"ML Model inference error: {e}")
                ml_reasons.append("ML_INFERENCE_ERROR")
        else:
            # Fallback mock ML Ensemble
            ml_buy = 0.35 if momentum > 0 else 0.20
            ml_sell = 0.35 if momentum < 0 else 0.20
            ml_conf = 0.55
            ml_reasons.append("ML_MOCK_FALLBACK")

        outputs["ml_ensemble"] = {
            "buy_prob": ml_buy,
            "sell_prob": ml_sell,
            "hold_prob": 1.0 - (ml_buy + ml_sell),
            "confidence": ml_conf,
            "expected_volatility": volatility,
            "expected_move": 0.0,
            "current_regime": ml_regime,
            "reason_codes": ml_reasons
        }

        return outputs
