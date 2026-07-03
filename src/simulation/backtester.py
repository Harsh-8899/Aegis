import numpy as np
import polars as pl
import pandas as pd
from typing import List, Dict, Any

class Backtester:
    """
    Institutional-grade historical backtesting engine.
    Simulates variable spreads, latency, slippage, execution commissions, 
    and computes advanced risk-adjusted performance metrics.
    """
    def __init__(self, initial_capital: float = 100000.0, commission_per_lot: float = 7.0, 
                 base_spread_pips: float = 1.5, leverage: float = 10.0):
        self.initial_capital = initial_capital
        self.commission_per_lot = commission_per_lot  # Standard round-turn lot commission (typically $7 on Gold)
        self.base_spread_pips = base_spread_pips      # 1 pip on Gold = $0.10
        self.leverage = leverage
        self.pip_value_multiplier = 0.10             # Gold standard lot (100 oz): 1 pip move = $10 (or 0.10 per 0.01 lot)

    def run(self, df: pl.DataFrame, signals: List[int], slippage_mean_pips: float = 1.0, 
            latency_ms: int = 150) -> Dict[str, Any]:
        """
        Executes a historical simulation.
        df: Polars DataFrame containing 'timestamp', 'open', 'high', 'low', 'close', 'atr_14'
        signals: List of integer signals corresponding to df length (1 = BUY, -1 = SELL, 0 = FLAT)
        """
        if len(signals) != df.height:
            raise ValueError("Signals array length must match DataFrame height.")

        # Convert to pandas or numpy arrays for fast sequential execution simulation
        timestamps = df["timestamp"].to_list()
        opens = df["open"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        atrs = df["atr_14"].to_numpy() if "atr_14" in df.columns else np.ones(df.height) * 1.5

        capital = self.initial_capital
        equity = [capital]
        drawdowns = [0.0]
        
        position = 0.0          # Current open lot size (positive = buy, negative = sell)
        entry_price = 0.0
        trades = []
        peak_equity = capital

        for i in range(1, len(opens)):
            current_close = closes[i]
            current_atr = atrs[i]
            signal = signals[i - 1] # Signal is acted upon with 1-step execution latency (next bar open)

            # Mark-to-market unrealized profit/loss
            unrealized_pnl = 0.0
            if position > 0: # Long
                # PnL = (Current price - Entry price) * 100 (oz per standard lot) * positions
                unrealized_pnl = (current_close - entry_price) * 100.0 * position
            elif position < 0: # Short
                unrealized_pnl = (entry_price - current_close) * 100.0 * abs(position)

            current_equity = capital + unrealized_pnl
            equity.append(current_equity)

            if current_equity > peak_equity:
                peak_equity = current_equity
            
            dd = (peak_equity - current_equity) / peak_equity
            drawdowns.append(dd)

            # Signal execution logic
            # Simulating execution latency and slippage using volatility (ATR)
            volatility_slippage = np.random.exponential(scale=current_atr * 0.1)  # Higher ATR -> higher slippage
            base_slippage = (slippage_mean_pips * 0.1) # 1 pip = 0.10 USD
            total_slippage = base_slippage + volatility_slippage
            
            # Commission calculation (Standard lot = 100,000 unit baseline, on gold 1 lot is 100 oz)
            commission = self.commission_per_lot

            # Check if signal is changing the position state
            if signal == 1 and position <= 0: # Want to go LONG
                # 1. Close Short if open
                if position < 0:
                    exit_price = opens[i] + total_slippage + (self.base_spread_pips * 0.05)
                    realized_pnl = (entry_price - exit_price) * 100.0 * abs(position) - commission
                    capital += realized_pnl
                    trades.append({
                        "type": "SHORT_CLOSE",
                        "entry_time": timestamps[i - 1],
                        "exit_time": timestamps[i],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "volume": abs(position),
                        "pnl": realized_pnl
                    })
                    position = 0.0

                # 2. Open Long
                position = 1.0 # 1 standard lot for simplicity
                entry_price = opens[i] + total_slippage + (self.base_spread_pips * 0.05)
                capital -= commission # pay commission up front
                
            elif signal == -1 and position >= 0: # Want to go SHORT
                # 1. Close Long if open
                if position > 0:
                    exit_price = opens[i] - total_slippage - (self.base_spread_pips * 0.05)
                    realized_pnl = (exit_price - entry_price) * 100.0 * position - commission
                    capital += realized_pnl
                    trades.append({
                        "type": "LONG_CLOSE",
                        "entry_time": timestamps[i - 1],
                        "exit_time": timestamps[i],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "volume": position,
                        "pnl": realized_pnl
                    })
                    position = 0.0

                # 2. Open Short
                position = -1.0
                entry_price = opens[i] - total_slippage - (self.base_spread_pips * 0.05)
                capital -= commission
                
            elif signal == 0 and position != 0: # Go FLAT
                # Close current position
                if position > 0:
                    exit_price = opens[i] - total_slippage - (self.base_spread_pips * 0.05)
                    realized_pnl = (exit_price - entry_price) * 100.0 * position - commission
                    capital += realized_pnl
                    trades.append({
                        "type": "LONG_CLOSE",
                        "entry_time": timestamps[i - 1],
                        "exit_time": timestamps[i],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "volume": position,
                        "pnl": realized_pnl
                    })
                elif position < 0:
                    exit_price = opens[i] + total_slippage + (self.base_spread_pips * 0.05)
                    realized_pnl = (entry_price - exit_price) * 100.0 * abs(position) - commission
                    capital += realized_pnl
                    trades.append({
                        "type": "SHORT_CLOSE",
                        "entry_time": timestamps[i - 1],
                        "exit_time": timestamps[i],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "volume": abs(position),
                        "pnl": realized_pnl
                    })
                position = 0.0

        # Close any lingering trade at the end of data window
        if position != 0:
            exit_price = closes[-1]
            if position > 0:
                realized_pnl = (exit_price - entry_price) * 100.0 * position - commission
                trades.append({"type": "LONG_CLOSE", "entry_time": timestamps[-1], "exit_time": timestamps[-1], "entry_price": entry_price, "exit_price": exit_price, "volume": position, "pnl": realized_pnl})
            else:
                realized_pnl = (entry_price - exit_price) * 100.0 * abs(position) - commission
                trades.append({"type": "SHORT_CLOSE", "entry_time": timestamps[-1], "exit_time": timestamps[-1], "entry_price": entry_price, "exit_price": exit_price, "volume": abs(position), "pnl": realized_pnl})
            capital += realized_pnl
            equity.append(capital)
            drawdowns.append((peak_equity - capital) / peak_equity)
        else:
            equity.append(capital)
            drawdowns.append((peak_equity - capital) / peak_equity)

        # Performance calculations
        equity_series = pd.Series(equity)
        returns = equity_series.pct_change().dropna()
        
        total_return = (capital - self.initial_capital) / self.initial_capital
        max_dd = max(drawdowns)
        
        # Risk-free rate assumed at 4.0% annualized
        rf_daily = 0.04 / 252
        mean_return = returns.mean()
        std_return = returns.std()
        
        # Annualized Sharpe (assuming daily returns, 252 periods per year)
        sharpe = 0.0
        if std_return > 0:
            sharpe = (mean_return - rf_daily) / std_return * np.sqrt(252)

        # Sortino Ratio (Downside deviation only)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        sortino = 0.0
        if downside_std > 0:
            sortino = (mean_return - rf_daily) / downside_std * np.sqrt(252)

        # Calmar Ratio (Annualized Return / Max Drawdown)
        calmar = (total_return / max_dd) if max_dd > 0 else 0.0

        pnl_trades = [t["pnl"] for t in trades]
        win_rate = (sum(1 for p in pnl_trades if p > 0) / len(pnl_trades)) if pnl_trades else 0.0
        profit_factor = (sum(p for p in pnl_trades if p > 0) / abs(sum(p for p in pnl_trades if p < 0))) if sum(p for p in pnl_trades if p < 0) != 0 else 1.0

        return {
            "final_capital": capital,
            "total_return": total_return,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": len(trades),
            "trades": trades,
            "equity_curve": equity
        }
