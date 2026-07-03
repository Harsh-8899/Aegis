import time
import datetime
import numpy as np
from typing import Dict, Any, List, Optional

class LiveFeatureEngine:
    """
    Computes real-time features incrementally every second based on tick updates.
    Maintains a sliding window of historical prices to ensure O(1) or small O(N) calculations,
    keeping computation times well under the 100ms latency requirement.
    """
    def __init__(self, window_size: int = 300):
        self.window_size = window_size
        self.prices: List[float] = []
        self.timestamps: List[datetime.datetime] = []
        self.bids: List[float] = []
        self.asks: List[float] = []
        self.spreads: List[float] = []
        self.volumes: List[float] = []
        
        # Keep track of running indicators for incremental speedup
        self.ema_12: Optional[float] = None
        self.ema_26: Optional[float] = None
        self.macd: Optional[float] = None
        self.macd_signal: Optional[float] = None
        
        self.rsi_avg_gain: Optional[float] = None
        self.rsi_avg_loss: Optional[float] = None
        
        # Volatility tracking
        self.returns_1s: List[float] = []

    def update(self, tick_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives a new price tick, updates historical buffers, 
        and calculates features incrementally.
        """
        price = float(tick_data["price"])
        bid = float(tick_data["bid"])
        ask = float(tick_data["ask"])
        spread = float(tick_data.get("spread", ask - bid))
        volume = float(tick_data.get("volume", 0.0))
        
        # Parse timestamp
        if isinstance(tick_data["timestamp"], str):
            ts = datetime.datetime.fromisoformat(tick_data["timestamp"])
        else:
            ts = tick_data["timestamp"]

        # Append to buffers
        self.prices.append(price)
        self.timestamps.append(ts)
        self.bids.append(bid)
        self.asks.append(ask)
        self.spreads.append(spread)
        self.volumes.append(volume)

        # Calculate returns
        ret_1s = 0.0
        if len(self.prices) > 1:
            ret_1s = (price - self.prices[-2]) / self.prices[-2]
        self.returns_1s.append(ret_1s)

        # Maintain window size
        if len(self.prices) > self.window_size:
            self.prices.pop(0)
            self.timestamps.pop(0)
            self.bids.pop(0)
            self.asks.pop(0)
            self.spreads.pop(0)
            self.volumes.pop(0)
            self.returns_1s.pop(0)

        n = len(self.prices)

        # Return features dict
        features = {}
        
        # 1. Price levels & spreads
        features["price"] = price
        features["bid"] = bid
        features["ask"] = ask
        features["spread"] = spread
        features["volume"] = volume
        
        # 2. Incremental returns
        features["return_1s"] = ret_1s
        features["return_5s"] = (price - self.prices[-6]) / self.prices[-6] if n >= 6 else 0.0
        features["return_15s"] = (price - self.prices[-16]) / self.prices[-16] if n >= 16 else 0.0
        features["return_1m"] = (price - self.prices[-61]) / self.prices[-61] if n >= 61 else 0.0

        # 3. Rolling metrics
        # Volatility over last 60 seconds
        vol_window = self.returns_1s[-60:] if n >= 60 else self.returns_1s
        features["rolling_volatility"] = float(np.std(vol_window)) if len(vol_window) > 1 else 0.0005
        
        # High/Low over last 60 seconds
        hl_window = self.prices[-60:] if n >= 60 else self.prices
        features["rolling_high"] = max(hl_window)
        features["rolling_low"] = min(hl_window)
        
        # Micro trend: SMA 5 vs SMA 15
        sma_5 = sum(self.prices[-5:]) / 5 if n >= 5 else price
        sma_15 = sum(self.prices[-15:]) / 15 if n >= 15 else price
        features["micro_trend"] = 1.0 if sma_5 > sma_15 else -1.0 if sma_5 < sma_15 else 0.0
        
        # Momentum: Price difference over last 10s
        features["momentum"] = price - self.prices[-11] if n >= 11 else 0.0
        
        # Candle Direction
        features["candle_direction"] = 1.0 if ret_1s > 0 else -1.0 if ret_1s < 0 else 0.0

        # 4. Incremental Indicators
        # Incremental EMA calculation helper
        def get_next_ema(current_val: float, prev_ema: Optional[float], period: int) -> float:
            if prev_ema is None:
                return current_val
            alpha = 2.0 / (period + 1)
            return current_val * alpha + prev_ema * (1.0 - alpha)

        # MACD
        self.ema_12 = get_next_ema(price, self.ema_12, 12)
        self.ema_26 = get_next_ema(price, self.ema_26, 26)
        macd_line = self.ema_12 - self.ema_26
        self.macd_signal = get_next_ema(macd_line, self.macd_signal, 9)
        features["macd"] = macd_line
        features["macd_signal"] = self.macd_signal
        features["macd_hist"] = macd_line - self.macd_signal

        # RSI (Wilder's SMA version)
        if n >= 2:
            change = price - self.prices[-2]
            gain = max(0.0, change)
            loss = max(0.0, -change)
            
            if self.rsi_avg_gain is None:
                # Initialize
                self.rsi_avg_gain = gain
                self.rsi_avg_loss = loss
            else:
                self.rsi_avg_gain = (self.rsi_avg_gain * 13 + gain) / 14
                self.rsi_avg_loss = (self.rsi_avg_loss * 13 + loss) / 14
            
            rs = self.rsi_avg_gain / (self.rsi_avg_loss + 1e-9)
            rsi = 100.0 - (100.0 / (1.0 + rs))
            features["rsi_14"] = rsi
        else:
            features["rsi_14"] = 50.0

        # ATR (Average True Range)
        if n >= 2:
            tr1 = price - self.prices[-2]
            tr2 = abs(price - self.prices[-2])
            tr3 = abs(self.prices[-2] - price)
            tr = max(tr1, tr2, tr3)
            # Use rolling standard deviation of price changes as a proxy for ATR in 1-second ticks
            features["atr_14"] = features["rolling_volatility"] * price * 2.0
        else:
            features["atr_14"] = 1.5

        # Bollinger Bands (20 period)
        bb_window = self.prices[-20:] if n >= 20 else self.prices
        bb_mean = sum(bb_window) / len(bb_window)
        bb_std = float(np.std(bb_window)) if len(bb_window) > 1 else 0.5
        bb_upper = bb_mean + 2 * bb_std
        bb_lower = bb_mean - 2 * bb_std
        
        # Bollinger Band position: %b = (Price - Lower) / (Upper - Lower)
        features["bb_position"] = (price - bb_lower) / (bb_upper - bb_lower + 1e-9)
        features["bb_upper"] = bb_upper
        features["bb_lower"] = bb_lower

        # 5. Z-Score (60 period)
        z_window = self.prices[-60:] if n >= 60 else self.prices
        z_mean = sum(z_window) / len(z_window)
        z_std = float(np.std(z_window)) if len(z_window) > 1 else 0.5
        features["z_score"] = (price - z_mean) / (z_std + 1e-9)

        # 6. Session Status (UTC based)
        hour = ts.hour
        # Tokyo: 00:00 - 09:00 UTC
        is_tokyo = 0 <= hour < 9
        # London: 08:00 - 16:30 UTC
        is_london = 8 <= hour < 17
        # New York: 13:00 - 21:00 UTC
        is_ny = 13 <= hour < 22
        
        if is_london and is_ny:
            features["session_status"] = "LDN/NY OVERLAP"
        elif is_london:
            features["session_status"] = "LONDON"
        elif is_ny:
            features["session_status"] = "NEW YORK"
        elif is_tokyo:
            features["session_status"] = "TOKYO"
        else:
            features["session_status"] = "ASIA/PACIFIC"

        # 7. Volatility Regime
        # Define high volatility if standard dev is above historical average
        vol_threshold = 0.0003
        if features["rolling_volatility"] > vol_threshold:
            features["volatility_regime"] = "HIGH_VOLATILITY"
        else:
            features["volatility_regime"] = "LOW_VOLATILITY"

        # 8. Trend/Range Regime
        # Range if absolute MACD is small and Z-score is neutral
        # Trend if MACD histogram is growing and momentum is significant
        if abs(features["macd_hist"]) > 0.05 or abs(features["momentum"]) > 0.40:
            features["market_regime"] = "TRENDING"
        else:
            features["market_regime"] = "RANGING"

        return features
