import polars as pl
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseStrategy(ABC):
    """
    Abstract base class for all XAU/USD trading strategies.
    """
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config

    @abstractmethod
    def generate_signal(self, df: pl.DataFrame) -> int:
        """
        Generates trading signal based on historical feature DataFrame.
        Returns:
            1: BUY / LONG signal
           -1: SELL / SHORT signal
            0: FLAT / NO POSITION signal
        """
        pass

class TrendFollowingStrategy(BaseStrategy):
    """
    Simple Moving Average (SMA) crossover trend following strategy.
    """
    def generate_signal(self, df: pl.DataFrame) -> int:
        if df.height < 50:
            return 0
            
        latest = df.tail(1).to_dicts()[0]
        
        # SMA Crossover check: Fast SMA (10) above Slow SMA (50) -> BUY
        fast_sma = latest.get("close_sma_10")
        slow_sma = latest.get("close_sma_50")
        close = latest.get("close")
        
        if fast_sma is None or slow_sma is None or close is None:
            return 0
            
        if fast_sma > slow_sma and close > fast_sma:
            return 1
        elif fast_sma < slow_sma and close < fast_sma:
            return -1
        return 0

class MeanReversionStrategy(BaseStrategy):
    """
    Bollinger Bands mean reversion strategy.
    """
    def generate_signal(self, df: pl.DataFrame) -> int:
        if df.height < 20:
            return 0
            
        latest = df.tail(1).to_dicts()[0]
        
        close = latest.get("close")
        upper_bb = latest.get("close_bb_upper_20")
        lower_bb = latest.get("close_bb_lower_20")
        rsi = latest.get("close_rsi_14")
        
        if close is None or upper_bb is None or lower_bb is None or rsi is None:
            return 0
            
        # Buy oversold at lower band, sell overbought at upper band
        if close <= lower_bb and rsi <= 30:
            return 1
        elif close >= upper_bb and rsi >= 70:
            return -1
        return 0

class VolatilityBreakoutStrategy(BaseStrategy):
    """
    ATR-based volatility breakout strategy.
    """
    def generate_signal(self, df: pl.DataFrame) -> int:
        if df.height < 15:
            return 0
            
        # Get latest and previous bars
        tail = df.tail(2).to_dicts()
        if len(tail) < 2:
            return 0
            
        prev, latest = tail[0], tail[1]
        
        close = latest.get("close")
        prev_high = prev.get("high")
        prev_low = prev.get("low")
        atr = latest.get("atr_14")
        
        if close is None or prev_high is None or prev_low is None or atr is None:
            return 0
            
        # Breakout if price exceeds previous high/low by more than 0.5 ATR
        breakout_threshold = 0.5 * atr
        
        if close > (prev_high + breakout_threshold):
            return 1
        elif close < (prev_low - breakout_threshold):
            return -1
        return 0
