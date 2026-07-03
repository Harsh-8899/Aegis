import logging
from typing import Dict, Any, List

logger = logging.getLogger("SignalFusion")

class SignalFusionEngine:
    """
    Combines outputs of various quant models into a single unified market signal.
    Applies weighted consensus rules, measures model agreement, computes confidence,
    and suggests target bounds.
    """
    def __init__(self):
        # Weights for models (sum to 1.0)
        self.weights = {
            "ml_ensemble": 0.30,
            "kalman": 0.15,
            "hmm": 0.15,
            "z_score_mr": 0.15,
            "momentum": 0.15,
            "breakout": 0.10
        }
        self.signal_threshold = 0.48  # Threshold to cross to trigger BUY or SELL

    def fuse_signals(self, model_outputs: Dict[str, Dict[str, Any]], current_price: float, atr: float) -> Dict[str, Any]:
        """
        Merges probabilities from models and computes a single fused decision.
        """
        fused_buy = 0.0
        fused_sell = 0.0
        fused_hold = 0.0
        
        # Track agreement
        decisions = []
        
        for model_name, weight in self.weights.items():
            out = model_outputs.get(model_name)
            if out:
                fused_buy += out["buy_prob"] * weight
                fused_sell += out["sell_prob"] * weight
                fused_hold += out["hold_prob"] * weight
                
                # Determine individual model choice
                p_buy = out["buy_prob"]
                p_sell = out["sell_prob"]
                p_hold = out["hold_prob"]
                if p_buy > p_sell and p_buy > p_hold:
                    decisions.append("BUY")
                elif p_sell > p_buy and p_sell > p_hold:
                    decisions.append("SELL")
                else:
                    decisions.append("HOLD")

        # Agreement ratio (how many active models agree on the final signal)
        total_agree = 0
        
        # Determine direction bias & signal
        final_signal = "HOLD"
        confidence = fused_hold
        direction_bias = "NEUTRAL"
        
        if fused_buy > fused_sell and fused_buy > fused_hold:
            direction_bias = "BULLISH"
            if fused_buy >= self.signal_threshold:
                final_signal = "BUY"
                confidence = fused_buy
                total_agree = decisions.count("BUY")
        elif fused_sell > fused_buy and fused_sell > fused_hold:
            direction_bias = "BEARISH"
            if fused_sell >= self.signal_threshold:
                final_signal = "SELL"
                confidence = fused_sell
                total_agree = decisions.count("SELL")
        else:
            direction_bias = "NEUTRAL"
            final_signal = "HOLD"
            confidence = fused_hold
            total_agree = decisions.count("HOLD")

        model_agreement_pct = round((total_agree / len(decisions)) * 100, 2) if decisions else 0.0

        # Expected volatility and Risk Score
        expected_vol = model_outputs["garch"]["expected_volatility"]
        # Volatility regime
        vol_state = "NORMAL"
        if expected_vol > 0.0015:
            vol_state = "SPIKE"
        elif expected_vol > 0.0008:
            vol_state = "HIGH"
            
        # Risk Score (0 to 100 based on volatility and spread)
        spread = model_outputs.get("z_score_mr", {}).get("spread", 0.18)
        risk_score = min(100.0, (expected_vol / 0.003) * 60.0 + (spread / 0.3) * 40.0)
        risk_score = round(risk_score, 2)

        # Trend Strength
        # Count how many trend models are bullish
        trend_models_agree = 0
        if model_outputs.get("kalman", {}).get("current_regime") == "UPTREND":
            trend_models_agree += 1
        if model_outputs.get("momentum", {}).get("current_regime") == "BULLISH_MOMENTUM":
            trend_models_agree += 1
        if model_outputs.get("hmm", {}).get("current_regime") == "LOW_VOL_BULLISH":
            trend_models_agree += 1

        trend_strength = "WEAK"
        if trend_models_agree == 3:
            trend_strength = "STRONG_UPTREND"
        elif trend_models_agree == 2:
            trend_strength = "MODERATE_UPTREND"
        elif trend_models_agree == 0:
            trend_strength = "STRONG_DOWNTREND"
        elif trend_models_agree == 1:
            trend_strength = "MODERATE_DOWNTREND"

        # Suggested stop-loss & take-profit bounds
        sl_range = [0.0, 0.0]
        tp_range = [0.0, 0.0]
        atr_val = atr if atr > 0 else 1.5
        
        if final_signal == "BUY":
            sl_range = [round(current_price - 2.5 * atr_val, 2), round(current_price - 1.5 * atr_val, 2)]
            tp_range = [round(current_price + 3.0 * atr_val, 2), round(current_price + 5.0 * atr_val, 2)]
        elif final_signal == "SELL":
            sl_range = [round(current_price + 1.5 * atr_val, 2), round(current_price + 2.5 * atr_val, 2)]
            tp_range = [round(current_price - 5.0 * atr_val, 2), round(current_price - 3.0 * atr_val, 2)]

        # Reason for signal
        reasons = []
        if final_signal == "BUY":
            reasons.append("CONSENSUS_BULLISH")
            if model_outputs["kalman"]["buy_prob"] > 0.6: reasons.append("KALMAN_SUPPORT")
            if model_outputs["z_score_mr"]["buy_prob"] > 0.6: reasons.append("OVERSOLD_REVERSION")
        elif final_signal == "SELL":
            reasons.append("CONSENSUS_BEARISH")
            if model_outputs["kalman"]["sell_prob"] > 0.6: reasons.append("KALMAN_SUPPORT")
            if model_outputs["z_score_mr"]["sell_prob"] > 0.6: reasons.append("OVERBOUGHT_REVERSION")
        else:
            reasons.append("HIGH_UNCERTAINTY_HOLD")
            if expected_vol > 0.0015:
                reasons.append("VOLATILITY_LOCKOUT")

        # Current regime
        current_regime = model_outputs["hmm"]["current_regime"]

        return {
            "signal": final_signal,
            "direction_bias": direction_bias,
            "confidence": round(confidence, 4),
            "risk_score": risk_score,
            "volatility_state": vol_state,
            "trend_strength": trend_strength,
            "suggested_sl_range": sl_range,
            "suggested_tp_range": tp_range,
            "reason": ", ".join(reasons),
            "model_agreement_pct": model_agreement_pct,
            "market_regime": current_regime
        }
