import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

class KalmanFilterPriceTracker:
    """
    1D Kalman Filter for adaptive trend tracking of asset prices.
    """
    def __init__(self, process_noise: float = 0.02, measurement_noise: float = 0.2):
        self.Q = process_noise
        self.R = measurement_noise
        self.x = None
        self.P = 1.0

    def update(self, price: float) -> float:
        if self.x is None:
            self.x = price
            return self.x
        P_pred = self.P + self.Q
        K = P_pred / (P_pred + self.R)
        self.x = self.x + K * (price - self.x)
        self.P = (1.0 - K) * P_pred
        return float(self.x)

    def predict(self, price: float, returns: np.ndarray, **kwargs) -> dict:
        filtered = self.update(price)
        diff = price - filtered
        std = np.sqrt(self.P + self.Q)
        
        # Calculate probability using normal distribution CDF
        z = diff / (std + 1e-9)
        buy_prob = float(norm.cdf(z))
        sell_prob = 1.0 - buy_prob
        
        # Scale to include hold region when near trend line
        hold_prob = 0.0
        if abs(z) < 0.5:
            hold_prob = 0.5 * (1.0 - abs(z)/0.5)
            buy_prob *= (1.0 - hold_prob)
            sell_prob *= (1.0 - hold_prob)

        confidence = float(min(0.95, 0.5 + abs(buy_prob - 0.5)))
        return {
            "buy_prob": buy_prob,
            "sell_prob": sell_prob,
            "hold_prob": hold_prob,
            "confidence": confidence,
            "expected_move": float(diff),
            "expected_volatility": float(std),
            "current_regime": "UPTREND" if diff > 0 else "DOWNTREND",
            "reason_codes": ["KALMAN_TREND_ABOVE"] if diff > 0 else ["KALMAN_TREND_BELOW"]
        }


class GARCHVolatilityForecaster:
    """
    GARCH(1,1) Volatility Forecaster.
    """
    def __init__(self):
        self.omega = 0.01
        self.alpha = 0.05
        self.beta = 0.90

    def _log_likelihood(self, params: np.ndarray, returns: np.ndarray) -> float:
        omega, alpha, beta = params
        if omega <= 0 or alpha < 0 or beta < 0 or (alpha + beta) >= 1.0:
            return 1e10
        n = len(returns)
        variance = np.zeros(n)
        variance[0] = np.var(returns) if np.var(returns) > 0 else 1e-4
        for t in range(1, n):
            variance[t] = omega + alpha * (returns[t-1] ** 2) + beta * variance[t-1]
            if variance[t] <= 1e-6:
                variance[t] = 1e-6
        log_lik = -0.5 * np.sum(np.log(2 * np.pi) + np.log(variance) + (returns ** 2) / variance)
        return -log_lik

    def fit(self, returns: np.ndarray) -> bool:
        if len(returns) < 20:
            return False
        init_params = np.array([0.05 * np.var(returns), 0.10, 0.80])
        bounds = ((1e-8, None), (0.0, 1.0), (0.0, 1.0))
        res = minimize(self._log_likelihood, init_params, args=(returns,), bounds=bounds, method="L-BFGS-B")
        if res.success:
            self.omega, self.alpha, self.beta = res.x
            return True
        return False

    def forecast_next_variance(self, returns: np.ndarray) -> float:
        if len(returns) == 0:
            return 1e-4
        self.fit(returns)
        n = len(returns)
        variance = np.zeros(n)
        variance[0] = np.var(returns) if np.var(returns) > 0 else 1e-4
        for t in range(1, n):
            variance[t] = self.omega + self.alpha * (returns[t-1] ** 2) + self.beta * variance[t-1]
            if variance[t] <= 1e-6:
                variance[t] = 1e-6
        next_var = self.omega + self.alpha * (returns[-1] ** 2) + self.beta * variance[-1]
        return float(next_var)

    def predict(self, price: float, returns: np.ndarray, **kwargs) -> dict:
        vol = 0.0005
        if len(returns) >= 20:
            try:
                vol = float(np.sqrt(self.forecast_next_variance(returns)))
            except Exception:
                pass
        return {
            "buy_prob": 0.33,
            "sell_prob": 0.33,
            "hold_prob": 0.34,
            "confidence": 0.60,
            "expected_move": 0.0,
            "expected_volatility": vol,
            "reason_codes": ["GARCH_VOLATILITY_EXPANDING"] if vol > 0.001 else ["GARCH_VOLATILITY_STABLE"]
        }


class HiddenMarkovModel:
    """
    2-State Gaussian Hidden Markov Model (Regime Detector).
    """
    def __init__(self):
        self.A = np.array([[0.95, 0.05], [0.10, 0.90]])
        self.means = np.array([0.0001, -0.0002])
        self.variances = np.array([0.0001, 0.0005])

    def fit(self, returns: np.ndarray):
        if len(returns) < 30:
            return
        rolling_std = np.array([np.std(returns[max(0, i-5):i+1]) for i in range(len(returns))])
        threshold = np.median(rolling_std)
        state0 = returns[rolling_std <= threshold]
        state1 = returns[rolling_std > threshold]
        if len(state0) > 2 and len(state1) > 2:
            self.means[0] = np.mean(state0)
            self.means[1] = np.mean(state1)
            self.variances[0] = np.var(state0) if np.var(state0) > 0 else 1e-5
            self.variances[1] = np.var(state1) if np.var(state1) > 0 else 1e-4

    def predict(self, price: float, returns: np.ndarray, **kwargs) -> dict:
        n = len(returns)
        hmm_regime = "LOW_VOL_BULLISH"
        buy_prob, sell_prob = 0.5, 0.3
        confidence = 0.50
        
        if n >= 30:
            self.fit(returns)
            log_A = np.log(self.A)
            viterbi = np.zeros((2, n))
            backpointer = np.zeros((2, n), dtype=int)
            p_emit_0 = norm.logpdf(returns[0], loc=self.means[0], scale=np.sqrt(self.variances[0]))
            p_emit_1 = norm.logpdf(returns[0], loc=self.means[1], scale=np.sqrt(self.variances[1]))
            viterbi[0, 0] = np.log(0.5) + p_emit_0
            viterbi[1, 0] = np.log(0.5) + p_emit_1

            for t in range(1, n):
                p0 = norm.logpdf(returns[t], loc=self.means[0], scale=np.sqrt(self.variances[0]))
                p1 = norm.logpdf(returns[t], loc=self.means[1], scale=np.sqrt(self.variances[1]))
                for s in range(2):
                    prob_from_0 = viterbi[0, t-1] + log_A[0, s]
                    prob_from_1 = viterbi[1, t-1] + log_A[1, s]
                    if prob_from_0 > prob_from_1:
                        viterbi[s, t] = prob_from_0 + (p0 if s == 0 else p1)
                        backpointer[s, t] = 0
                    else:
                        viterbi[s, t] = prob_from_1 + (p0 if s == 0 else p1)
                        backpointer[s, t] = 1

            current_state = int(np.argmax(viterbi[:, -1]))
            if current_state == 0:
                hmm_regime = "LOW_VOL_BULLISH"
                buy_prob, sell_prob = 0.70, 0.10
                confidence = 0.80
            else:
                hmm_regime = "HIGH_VOL_BEARISH"
                buy_prob, sell_prob = 0.10, 0.70
                confidence = 0.85

        return {
            "buy_prob": buy_prob,
            "sell_prob": sell_prob,
            "hold_prob": 1.0 - (buy_prob + sell_prob),
            "confidence": confidence,
            "expected_move": float(self.means[0] if hmm_regime == "LOW_VOL_BULLISH" else self.means[1]) * price,
            "expected_volatility": float(np.sqrt(self.variances[0] if hmm_regime == "LOW_VOL_BULLISH" else self.variances[1])),
            "current_regime": hmm_regime,
            "reason_codes": [f"HMM_REGIME_{hmm_regime}"]
        }


class AutoRegressiveModel:
    """
    AR(3) Baseline Return Forecast.
    """
    def __init__(self, lags: int = 3):
        self.lags = lags
        self.coefficients = None
        self.intercept = 0.0

    def fit(self, returns: np.ndarray) -> bool:
        n = len(returns)
        if n <= self.lags + 3:
            return False
        Y = returns[self.lags:]
        X = np.zeros((n - self.lags, self.lags + 1))
        X[:, 0] = 1.0
        for i in range(self.lags):
            X[:, i + 1] = returns[self.lags - 1 - i : n - 1 - i]
        try:
            beta = np.linalg.pinv(X.T @ X) @ X.T @ Y
            self.intercept = float(beta[0])
            self.coefficients = beta[1:]
            return True
        except Exception:
            return False

    def predict(self, price: float, returns: np.ndarray, **kwargs) -> dict:
        pred_ret = 0.0
        if len(returns) >= self.lags + 2:
            if self.fit(returns):
                lag_features = returns[-self.lags:][::-1]
                pred_ret = self.intercept + np.dot(self.coefficients, lag_features)
        
        buy_prob = 0.33
        sell_prob = 0.33
        if pred_ret > 0.0001:
            buy_prob = 0.65
            sell_prob = 0.15
        elif pred_ret < -0.0001:
            buy_prob = 0.15
            sell_prob = 0.65

        return {
            "buy_prob": buy_prob,
            "sell_prob": sell_prob,
            "hold_prob": 1.0 - (buy_prob + sell_prob),
            "confidence": 0.68,
            "expected_move": float(pred_ret * price),
            "expected_volatility": float(np.std(returns)) if len(returns) > 1 else 0.0005,
            "reason_codes": ["AR_PREDICTED_UP"] if pred_ret > 0 else ["AR_PREDICTED_DOWN"]
        }


class BayesianUncertaintyEstimator:
    """
    Bayesian conjugate update model to estimate likelihood of price increases.
    """
    def predict(self, price: float, returns: np.ndarray, **kwargs) -> dict:
        if len(returns) < 5:
            return {"buy_prob": 0.33, "sell_prob": 0.33, "hold_prob": 0.34, "confidence": 0.50, "expected_move": 0.0, "expected_volatility": 0.0005, "reason_codes": ["BAYES_INSUFFICIENT_DATA"]}
        
        s = np.std(returns) if np.std(returns) > 0 else 0.0005
        # Posterior precision with normal likelihood & conjugate normal prior
        tau_0 = 1.0
        tau_post = tau_0 + len(returns) / (s**2)
        mu_post = (np.sum(returns) / (s**2)) / tau_post
        
        sigma_post = np.sqrt(1.0 / tau_post)
        prob_positive = float(norm.cdf(mu_post / (sigma_post + 1e-9)))
        
        buy_prob = prob_positive
        sell_prob = 1.0 - buy_prob
        
        return {
            "buy_prob": buy_prob,
            "sell_prob": sell_prob,
            "hold_prob": 0.0,
            "confidence": float(min(0.95, 0.5 + abs(buy_prob - 0.5))),
            "expected_move": float(mu_post * price),
            "expected_volatility": float(sigma_post),
            "reason_codes": ["BAYES_UNCERTAINTY_UP"] if buy_prob > 0.5 else ["BAYES_UNCERTAINTY_DOWN"]
        }


class MonteCarloPathSimulator:
    """
    Generates simulated paths to forecast potential tail drawdowns and expected outcomes.
    """
    def predict(self, price: float, returns: np.ndarray, **kwargs) -> dict:
        if len(returns) < 10:
            return {"buy_prob": 0.33, "sell_prob": 0.33, "hold_prob": 0.34, "confidence": 0.50, "expected_move": 0.0, "expected_volatility": 0.0005, "reason_codes": ["MC_INSUFFICIENT_DATA"]}
        
        mean_ret = np.mean(returns)
        std_ret = np.std(returns) if np.std(returns) > 0 else 0.0005
        
        # Run 100 paths of 30 steps
        num_paths = 100
        steps = 30
        sim_ends = []
        for _ in range(num_paths):
            rand = np.random.normal(mean_ret, std_ret, steps)
            sim_ends.append(price * np.exp(np.sum(rand)))
            
        pos_paths = sum(1 for p in sim_ends if p > price)
        buy_prob = pos_paths / num_paths
        
        return {
            "buy_prob": buy_prob,
            "sell_prob": 1.0 - buy_prob,
            "hold_prob": 0.0,
            "confidence": 0.70,
            "expected_move": float(np.mean(sim_ends) - price),
            "expected_volatility": float(std_ret),
            "reason_codes": ["MC_POTENTIAL_GAIN"] if buy_prob > 0.5 else ["MC_POTENTIAL_LOSS"]
        }


class ZScoreMeanReversionModel:
    """
    Mean reversion strategy triggered by statistical z-score price bands.
    """
    def predict(self, price: float, returns: np.ndarray, z_score: float = 0.0, **kwargs) -> dict:
        buy_prob = 0.33
        sell_prob = 0.33
        reasons = ["ZSCORE_NEUTRAL"]
        
        if z_score < -2.0:
            buy_prob = min(0.90, 0.5 - z_score * 0.15)
            sell_prob = 0.05
            reasons = ["ZSCORE_OVERSOLD_REVERSION"]
        elif z_score > 2.0:
            sell_prob = min(0.90, 0.5 + z_score * 0.15)
            buy_prob = 0.05
            reasons = ["ZSCORE_OVERBOUGHT_REVERSION"]

        return {
            "buy_prob": buy_prob,
            "sell_prob": sell_prob,
            "hold_prob": 1.0 - (buy_prob + sell_prob),
            "confidence": 0.75 if abs(z_score) > 2.0 else 0.50,
            "expected_move": float(-z_score * 0.10 * price * 0.001), # revert direction
            "expected_volatility": float(np.std(returns)) if len(returns) > 1 else 0.0005,
            "reason_codes": reasons
        }


class MomentumOscillatorModel:
    """
    Momentum trend model analyzing price velocity.
    """
    def predict(self, price: float, returns: np.ndarray, momentum: float = 0.0, **kwargs) -> dict:
        buy_prob = 0.33
        sell_prob = 0.33
        reasons = ["MOMENTUM_STABLE"]
        mom_regime = "FLAT"
        
        if momentum > 0.5:
            buy_prob = 0.75
            sell_prob = 0.10
            reasons = ["STRONG_BULLISH_MOMENTUM"]
            mom_regime = "BULLISH_MOMENTUM"
        elif momentum < -0.5:
            buy_prob = 0.10
            sell_prob = 0.75
            reasons = ["STRONG_BEARISH_MOMENTUM"]
            mom_regime = "BEARISH_MOMENTUM"

        return {
            "buy_prob": buy_prob,
            "sell_prob": sell_prob,
            "hold_prob": 1.0 - (buy_prob + sell_prob),
            "confidence": 0.70,
            "expected_move": float(momentum),
            "expected_volatility": float(np.std(returns)) if len(returns) > 1 else 0.0005,
            "current_regime": mom_regime,
            "reason_codes": reasons
        }


class BreakoutProbabilityModel:
    """
    Bollinger band breakout probability predictor.
    """
    def predict(self, price: float, returns: np.ndarray, bb_pos: float = 0.5, **kwargs) -> dict:
        buy_prob = 0.10
        sell_prob = 0.10
        reasons = ["BO_INSIDE_BB"]
        
        if bb_pos > 1.0:
            buy_prob = 0.85
            reasons = ["BO_BULLISH_BB_BREAKOUT"]
        elif bb_pos < 0.0:
            sell_prob = 0.85
            reasons = ["BO_BEARISH_BB_BREAKOUT"]

        return {
            "buy_prob": buy_prob,
            "sell_prob": sell_prob,
            "hold_prob": 1.0 - (buy_prob + sell_prob),
            "confidence": 0.72,
            "expected_move": float((bb_pos - 0.5) * 2.0),
            "expected_volatility": float(np.std(returns)) if len(returns) > 1 else 0.0005,
            "reason_codes": reasons
        }
