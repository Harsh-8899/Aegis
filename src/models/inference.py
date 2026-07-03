import logging
import numpy as np
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from src.models.math_models import KalmanFilterPriceTracker, GARCHVolatilityForecaster, HiddenMarkovModel
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
        filtered_price = self.kalman.update(price)
        kalman_diff = price - filtered_price
        # Buy if price is above filtered trend, sell if below
        kalman_buy = 0.8 if kalman_diff > 0.05 else 0.1
        kalman_sell = 0.8 if kalman_diff < -0.05 else 0.1
        kalman_hold = 1.0 - (kalman_buy + kalman_sell)
        outputs["kalman"] = {
            "buy_prob": kalman_buy,
            "sell_prob": kalman_sell,
            "hold_prob": kalman_hold,
            "confidence": 0.75,
            "expected_volatility": volatility,
            "current_regime": "UPTREND" if kalman_diff > 0 else "DOWNTREND",
            "reason_codes": ["KALMAN_TREND_ABOVE"] if kalman_diff > 0 else ["KALMAN_TREND_BELOW"]
        }

        # 2. EWMA Volatility
        if len(rets_arr) > 0:
            last_ret = rets_arr[-1]
            self.running_variance = self.ewma_decay * self.running_variance + (1 - self.ewma_decay) * (last_ret ** 2)
        ewma_vol = np.sqrt(self.running_variance)
        outputs["ewma_vol"] = {
            "buy_prob": 0.33, "sell_prob": 0.33, "hold_prob": 0.34,
            "confidence": 0.60,
            "expected_volatility": ewma_vol,
            "current_regime": "HIGH_VOL" if ewma_vol > 0.001 else "LOW_VOL",
            "reason_codes": ["EWMA_VOL_UPDATED"]
        }

        # 3. GARCH Volatility Forecast
        garch_vol = volatility
        try:
            if len(rets_arr) >= 30:
                garch_var = self.garch.forecast_next_variance(rets_arr)
                garch_vol = np.sqrt(garch_var)
        except Exception as e:
            logger.debug(f"GARCH calculation skipped: {e}")
            
        outputs["garch"] = {
            "buy_prob": 0.33, "sell_prob": 0.33, "hold_prob": 0.34,
            "confidence": 0.70,
            "expected_volatility": garch_vol,
            "current_regime": "HIGH_RISK" if garch_vol > 0.0015 else "STABLE",
            "reason_codes": ["GARCH_FORECAST_CALCULATED"]
        }

        # 4. Hidden Markov Model
        hmm_regime = "LOW_VOL_BULLISH"
        hmm_buy = 0.5
        hmm_sell = 0.3
        confidence = 0.50
        try:
            if len(rets_arr) >= 50:
                states = self.hmm.predict_regime_states(rets_arr)
                if len(states) > 0:
                    current_state = int(states[-1])
                    if current_state == 0:
                        hmm_regime = "LOW_VOL_BULLISH"
                        hmm_buy, hmm_sell = 0.7, 0.1
                        confidence = 0.80
                    else:
                        hmm_regime = "HIGH_VOL_BEARISH"
                        hmm_buy, hmm_sell = 0.1, 0.8
                        confidence = 0.85
        except Exception as e:
            logger.debug(f"HMM prediction failed: {e}")

        outputs["hmm"] = {
            "buy_prob": hmm_buy,
            "sell_prob": hmm_sell,
            "hold_prob": 1.0 - (hmm_buy + hmm_sell),
            "confidence": confidence,
            "expected_volatility": volatility,
            "current_regime": hmm_regime,
            "reason_codes": [f"HMM_REGIME_{hmm_regime}"]
        }

        # 5. Z-Score Mean Reversion Detector
        mr_buy, mr_sell = 0.1, 0.1
        mr_regime = "NEUTRAL"
        reasons = []
        if z_score < -2.0:
            mr_buy = 0.85
            mr_regime = "OVERSOLD"
            reasons.append("ZSCORE_OVERSOLD")
        elif z_score > 2.0:
            mr_sell = 0.85
            mr_regime = "OVERBOUGHT"
            reasons.append("ZSCORE_OVERBOUGHT")
        else:
            reasons.append("ZSCORE_NORMAL")
            
        outputs["z_score_mr"] = {
            "buy_prob": mr_buy,
            "sell_prob": mr_sell,
            "hold_prob": 1.0 - (mr_buy + mr_sell),
            "confidence": 0.80,
            "expected_volatility": volatility,
            "current_regime": mr_regime,
            "reason_codes": reasons
        }

        # 6. Momentum/Trend Detector
        mom_buy, mom_sell = 0.33, 0.33
        mom_regime = "FLAT"
        if momentum > 0.5:
            mom_buy = 0.75
            mom_sell = 0.05
            mom_regime = "BULLISH_MOMENTUM"
        elif momentum < -0.5:
            mom_buy = 0.05
            mom_sell = 0.75
            mom_regime = "BEARISH_MOMENTUM"
            
        outputs["momentum"] = {
            "buy_prob": mom_buy,
            "sell_prob": mom_sell,
            "hold_prob": 1.0 - (mom_buy + mom_sell),
            "confidence": 0.70,
            "expected_volatility": volatility,
            "current_regime": mom_regime,
            "reason_codes": [f"MOMENTUM_{mom_regime}"]
        }

        # 7. Breakout Probability Model
        bo_buy, bo_sell = 0.1, 0.1
        bo_regime = "CONSOLIDATION"
        reasons_bo = []
        if bb_pos > 1.0:
            bo_buy = 0.80
            bo_regime = "BULLISH_BREAKOUT"
            reasons_bo.append("BO_BB_UPPER_BREACH")
        elif bb_pos < 0.0:
            bo_sell = 0.80
            bo_regime = "BEARISH_BREAKOUT"
            reasons_bo.append("BO_BB_LOWER_BREACH")
        else:
            reasons_bo.append("BO_BB_NORMAL")
            
        outputs["breakout"] = {
            "buy_prob": bo_buy,
            "sell_prob": bo_sell,
            "hold_prob": 1.0 - (bo_buy + bo_sell),
            "confidence": 0.72,
            "expected_volatility": volatility,
            "current_regime": bo_regime,
            "reason_codes": reasons_bo
        }

        # 8. ML Ensemble Inference (RandomForest, ExtraTrees, GradientBoosting)
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
                    ml_reasons.append("ML_CONCENSUS_BUY")
                elif max_class == 0:
                    ml_regime = "ML_BEARISH"
                    ml_reasons.append("ML_CONCENSUS_SELL")
                else:
                    ml_regime = "ML_NEUTRAL"
                    ml_reasons.append("ML_CONCENSUS_HOLD")
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
            "current_regime": ml_regime,
            "reason_codes": ml_reasons
        }

        return outputs
