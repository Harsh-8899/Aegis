import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

class KalmanFilterPriceTracker:
    """
    1D Kalman Filter for adaptive trend tracking of asset prices.
    Filters market microstructure noise to estimate the true price level.
    """
    def __init__(self, process_noise: float = 0.05, measurement_noise: float = 0.5):
        self.Q = process_noise  # Process covariance (how fast true price changes)
        self.R = measurement_noise  # Measurement covariance (noise in price feed)
        self.x = None  # Estimated true price
        self.P = 1.0  # Estimation error covariance

    def update(self, price: float) -> float:
        """
        Updates filter state with a new price measurement.
        Returns the filtered estimate.
        """
        if self.x is None:
            self.x = price
            return self.x

        # 1. Predict state and covariance
        # State transitions: x_t = x_t-1
        P_pred = self.P + self.Q

        # 2. Update / Correct
        # Kalman Gain
        K = P_pred / (P_pred + self.R)
        # Update state estimate
        self.x = self.x + K * (price - self.x)
        # Update error covariance
        self.P = (1.0 - K) * P_pred

        return float(self.x)

    def run_series(self, prices: list[float] | np.ndarray) -> np.ndarray:
        """
        Runs Kalman filter over a series of price measurements.
        """
        filtered = []
        for p in prices:
            filtered.append(self.update(p))
        return np.array(filtered)


class GARCHVolatilityForecaster:
    """
    GARCH(1,1) Volatility Forecaster.
    Fits variance equation: sigma_t^2 = omega + alpha * r_t-1^2 + beta * sigma_t-1^2
    """
    def __init__(self):
        self.omega = 0.01
        self.alpha = 0.05
        self.beta = 0.90

    def _log_likelihood(self, params: np.ndarray, returns: np.ndarray) -> float:
        """
        Calculates negative log-likelihood of returns under GARCH(1,1).
        """
        omega, alpha, beta = params
        
        # Stability constraints checked by optimizer bounds, but add penalization here
        if omega <= 0 or alpha < 0 or beta < 0 or (alpha + beta) >= 1.0:
            return 1e10

        n = len(returns)
        variance = np.zeros(n)
        
        # Initialize variance to unconditional variance
        variance[0] = np.var(returns)
        if variance[0] == 0:
            variance[0] = 1e-4

        for t in range(1, n):
            variance[t] = omega + alpha * (returns[t-1] ** 2) + beta * variance[t-1]
            # Prevent division by zero
            if variance[t] <= 1e-6:
                variance[t] = 1e-6

        # Gaussian log likelihood formula sum
        log_lik = -0.5 * np.sum(np.log(2 * np.pi) + np.log(variance) + (returns ** 2) / variance)
        return -log_lik # Minimize negative log-likelihood

    def fit(self, returns: np.ndarray) -> bool:
        """
        Fits GARCH(1,1) model parameters using Scipy's L-BFGS-B optimizer.
        """
        if len(returns) < 30:
            return False # Insufficient data

        # Initial parameter guess
        init_params = np.array([0.05 * np.var(returns), 0.10, 0.80])
        bounds = ((1e-8, None), (0.0, 1.0), (0.0, 1.0))

        # Solve optimization
        res = minimize(
            self._log_likelihood,
            init_params,
            args=(returns,),
            bounds=bounds,
            method="L-BFGS-B"
        )

        if res.success:
            self.omega, self.alpha, self.beta = res.x
            return True
        return False

    def forecast_next_variance(self, returns: np.ndarray) -> float:
        """
        Forecasts next-period conditional variance.
        """
        if len(returns) == 0:
            return 1e-4
            
        # Fit model first
        self.fit(returns)
        
        # Calculate current state variance
        n = len(returns)
        variance = np.zeros(n)
        variance[0] = np.var(returns) if np.var(returns) > 0 else 1e-4
        
        for t in range(1, n):
            variance[t] = self.omega + self.alpha * (returns[t-1] ** 2) + self.beta * variance[t-1]
            if variance[t] <= 1e-6:
                variance[t] = 1e-6

        # Forecast next variance
        next_var = self.omega + self.alpha * (returns[-1] ** 2) + self.beta * variance[-1]
        return float(next_var)


class HiddenMarkovModel:
    """
    2-State Gaussian Hidden Markov Model (Regime Detector).
    State 0: Low Volatility / Bullish trend
    State 1: High Volatility / Bearish trend
    """
    def __init__(self):
        # Transition matrix (probability of switching states)
        self.A = np.array([[0.95, 0.05], 
                           [0.10, 0.90]])
        # Means and variances for returns in each state
        self.means = np.array([0.0001, -0.0002])
        self.variances = np.array([0.0001, 0.0005])

    def fit(self, returns: np.ndarray):
        """
        Fits emission parameters based on empirical splits (K-Means style initial clustering).
        """
        if len(returns) < 50:
            return
            
        # Segment returns into high and low volatility subsets
        rolling_std = np.array([np.std(returns[max(0, i-10):i+1]) for i in range(len(returns))])
        threshold = np.median(rolling_std)
        
        state0_returns = returns[rolling_std <= threshold]
        state1_returns = returns[rolling_std > threshold]
        
        if len(state0_returns) > 5 and len(state1_returns) > 5:
            self.means[0] = np.mean(state0_returns)
            self.means[1] = np.mean(state1_returns)
            self.variances[0] = np.var(state0_returns) if np.var(state0_returns) > 0 else 1e-5
            self.variances[1] = np.var(state1_returns) if np.var(state1_returns) > 0 else 1e-4

    def predict_regime_states(self, returns: np.ndarray) -> np.ndarray:
        """
        Implements the classical Viterbi Algorithm to find the most likely
        sequence of hidden states (0 or 1) for a given returns series.
        """
        n = len(returns)
        if n == 0:
            return np.array([])
            
        self.fit(returns)

        # 1. Initialize variables
        # Log scales to avoid floating-point underflow
        log_A = np.log(self.A)
        
        viterbi = np.zeros((2, n))
        backpointer = np.zeros((2, n), dtype=int)

        # Emission probability logs
        # norm.pdf(x, loc, scale)
        p_emit_0 = norm.logpdf(returns[0], loc=self.means[0], scale=np.sqrt(self.variances[0]))
        p_emit_1 = norm.logpdf(returns[0], loc=self.means[1], scale=np.sqrt(self.variances[1]))

        # Assume uniform initial state probabilities (0.5 each)
        viterbi[0, 0] = np.log(0.5) + p_emit_0
        viterbi[1, 0] = np.log(0.5) + p_emit_1

        # 2. Viterbi recursion
        for t in range(1, n):
            p0 = norm.logpdf(returns[t], loc=self.means[0], scale=np.sqrt(self.variances[0]))
            p1 = norm.logpdf(returns[t], loc=self.means[1], scale=np.sqrt(self.variances[1]))

            for s in range(2):
                # Calculate paths from state 0 and state 1 to state s
                prob_from_0 = viterbi[0, t-1] + log_A[0, s]
                prob_from_1 = viterbi[1, t-1] + log_A[1, s]
                
                if prob_from_0 > prob_from_1:
                    viterbi[s, t] = prob_from_0 + (p0 if s == 0 else p1)
                    backpointer[s, t] = 0
                else:
                    viterbi[s, t] = prob_from_1 + (p0 if s == 0 else p1)
                    backpointer[s, t] = 1

        # 3. Backtracking
        states = np.zeros(n, dtype=int)
        states[-1] = np.argmax(viterbi[:, -1])

        for t in range(n - 2, -1, -1):
            states[t] = backpointer[states[t+1], t+1]

        return states


class AutoRegressiveModel:
    """
    AR(p) AutoRegressive returns predictor using rolling Ordinary Least Squares (OLS).
    r_t = c + phi_1 * r_t-1 + ... + phi_p * r_t-p
    """
    def __init__(self, lags: int = 3):
        self.lags = lags
        self.coefficients = None
        self.intercept = 0.0

    def fit(self, returns: np.ndarray) -> bool:
        """
        Fits AR(p) coefficients using standard linear algebra OLS solver.
        """
        n = len(returns)
        if n <= self.lags + 5:
            return False

        # Construct Y target vector and X lag matrix
        Y = returns[self.lags:]
        X = np.zeros((n - self.lags, self.lags + 1))
        X[:, 0] = 1.0  # Intercept column
        
        for i in range(self.lags):
            # Fill lag columns (lag_1, lag_2...)
            X[:, i + 1] = returns[self.lags - 1 - i : n - 1 - i]

        try:
            # Solve OLS: beta = (X^T X)^-1 X^T Y
            # Using pinv (pseudo-inverse) for extreme stability against multicollinearity
            beta = np.linalg.pinv(X.T @ X) @ X.T @ Y
            self.intercept = float(beta[0])
            self.coefficients = beta[1:]
            return True
        except Exception:
            return False

    def predict_next_return(self, returns: np.ndarray) -> float:
        """
        Predicts returns for time t+1 using fitted coefficients.
        """
        if len(returns) < self.lags + 2:
            return 0.0
            
        # Fit coefficients
        success = self.fit(returns)
        if not success or self.coefficients is None:
            return 0.0

        # Construct recent lag vector
        lag_features = returns[-self.lags:][::-1] # Reverse lag order
        prediction = self.intercept + np.dot(self.coefficients, lag_features)
        return float(prediction)
