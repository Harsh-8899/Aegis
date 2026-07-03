import numpy as np
import polars as pl
from typing import List, Dict, Any, Tuple
from src.simulation.backtester import Backtester

class WalkForwardValidator:
    """
    Splits data into walk-forward training/testing windows
    to validate strategies out-of-sample.
    """
    @staticmethod
    def get_slices(df: pl.DataFrame, train_size: int, test_size: int, step_size: int) -> List[Tuple[pl.DataFrame, pl.DataFrame]]:
        """
        Generates walk-forward (train, test) splits.
        """
        slices = []
        total_rows = df.height
        
        start = 0
        while start + train_size + test_size <= total_rows:
            train_df = df.slice(start, train_size)
            test_df = df.slice(start + train_size, test_size)
            slices.append((train_df, test_df))
            start += step_size
            
        return slices

class MonteCarloSimulator:
    """
    Performs randomized path simulations to estimate drawdown distribution,
    VaR limits, and risk of ruin.
    """
    @staticmethod
    def simulate_paths(returns: np.ndarray, num_simulations: int = 1000, 
                       path_length: int = 252, initial_capital: float = 100000.0) -> Dict[str, Any]:
        """
        Runs Monte Carlo paths using bootstrapping of actual trade returns.
        """
        if len(returns) == 0:
            # Fallback to normal returns distribution if no actual trades have run
            returns = np.random.normal(0.0001, 0.005, 100)

        simulated_curves = np.zeros((num_simulations, path_length))
        max_drawdowns = np.zeros(num_simulations)
        ruin_count = 0
        half_ruin_count = 0 # 50% drawdown

        for s in range(num_simulations):
            # Bootstrap returns
            path_returns = np.random.choice(returns, size=path_length, replace=True)
            
            # Reconstruct equity curve
            equity_curve = initial_capital * np.cumprod(1.0 + path_returns)
            simulated_curves[s, :] = equity_curve
            
            # Calculate max drawdown for this path
            peaks = np.maximum.accumulate(equity_curve)
            drawdowns = (peaks - equity_curve) / peaks
            max_dd = np.max(drawdowns)
            max_drawdowns[s] = max_dd
            
            # Check ruin thresholds
            if np.min(equity_curve) < initial_capital * 0.1: # 90% loss
                ruin_count += 1
            if np.min(equity_curve) < initial_capital * 0.5: # 50% loss
                half_ruin_count += 1

        final_values = simulated_curves[:, -1]
        
        return {
            "percentile_5": np.percentile(final_values, 5),
            "percentile_50_median": np.percentile(final_values, 50),
            "percentile_95": np.percentile(final_values, 95),
            "mean_drawdown": np.mean(max_drawdowns),
            "drawdown_95_var": np.percentile(max_drawdowns, 95),
            "risk_of_ruin_pct": (ruin_count / num_simulations) * 100.0,
            "risk_of_50pct_drawdown_pct": (half_ruin_count / num_simulations) * 100.0,
            "simulated_curves": simulated_curves[:10].tolist()  # Sample 10 paths for dashboard charts
        }
