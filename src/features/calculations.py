import polars as pl
import numpy as np

class FeatureCalculator:
    """
    Computes technical, volatility, statistical, and regime features using Polars.
    """
    
    @staticmethod
    def compute_sma(df: pl.DataFrame, column: str, period: int) -> pl.DataFrame:
        return df.with_columns(
            pl.col(column).rolling_mean(window_size=period).alias(f"{column}_sma_{period}")
        )

    @staticmethod
    def compute_ema(df: pl.DataFrame, column: str, period: int) -> pl.DataFrame:
        # Pydantic or Polars does not have an EMA builtin directly in basic rolling, 
        # so we calculate it or approximate using rolling ewm if supported or custom loop.
        # Polars has `ewm_mean` on newer versions. Let's use `ewm_mean` or fallback to simple EMA.
        try:
            return df.with_columns(
                pl.col(column).ewm_mean(span=period, adjust=False).alias(f"{column}_ema_{period}")
            )
        except Exception:
            # Fallback to SMA if ewm_mean is not supported
            return FeatureCalculator.compute_sma(df, column, period)

    @staticmethod
    def compute_rsi(df: pl.DataFrame, column: str, period: int = 14) -> pl.DataFrame:
        """
        Computes Relative Strength Index (RSI).
        """
        # Calculate price changes
        close_diff = pl.col(column).diff()
        gain = pl.when(close_diff > 0).then(close_diff).otherwise(0.0)
        loss = pl.when(close_diff < 0).then(-close_diff).otherwise(0.0)

        # Average gains and losses
        avg_gain = gain.rolling_mean(window_size=period)
        avg_loss = loss.rolling_mean(window_size=period)

        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return df.with_columns(rsi.alias(f"{column}_rsi_{period}"))

    @staticmethod
    def compute_atr(df: pl.DataFrame, period: int = 14) -> pl.DataFrame:
        """
        Computes Average True Range (ATR).
        """
        # True Range calculation
        prev_close = pl.col("close").shift(1)
        tr1 = pl.col("high") - pl.col("low")
        tr2 = (pl.col("high") - prev_close).abs()
        tr3 = (pl.col("low") - prev_close).abs()
        
        # Max of the three
        tr = pl.max_horizontal(tr1, tr2, tr3)
        atr = tr.rolling_mean(window_size=period)
        
        return df.with_columns([
            tr.alias("true_range"),
            atr.alias(f"atr_{period}")
        ])

    @staticmethod
    def compute_bollinger_bands(df: pl.DataFrame, column: str, period: int = 20, num_std: float = 2.0) -> pl.DataFrame:
        """
        Computes Bollinger Bands (Upper, Lower, Width).
        """
        sma = pl.col(column).rolling_mean(window_size=period)
        std = pl.col(column).rolling_std(window_size=period)
        
        upper = sma + (num_std * std)
        lower = sma - (num_std * std)
        band_width = (upper - lower) / (sma + 1e-9)
        
        return df.with_columns([
            upper.alias(f"{column}_bb_upper_{period}"),
            lower.alias(f"{column}_bb_lower_{period}"),
            band_width.alias(f"{column}_bb_width_{period}")
        ])

    @staticmethod
    def compute_macd(df: pl.DataFrame, column: str, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> pl.DataFrame:
        """
        Computes MACD and MACD Signal line.
        """
        df = FeatureCalculator.compute_ema(df, column, fast_period)
        df = FeatureCalculator.compute_ema(df, column, slow_period)
        
        macd_line = pl.col(f"{column}_ema_{fast_period}") - pl.col(f"{column}_ema_{slow_period}")
        
        # Add temporary macd_line to compute its signal line
        df = df.with_columns(macd_line.alias("macd_line_temp"))
        
        # Compute signal line on the temporary column
        df = FeatureCalculator.compute_ema(df, "macd_line_temp", signal_period)
        
        # Rename columns to standard names and drop temp
        df = df.with_columns([
            pl.col("macd_line_temp").alias(f"{column}_macd"),
            pl.col(f"macd_line_temp_ema_{signal_period}").alias(f"{column}_macd_signal")
        ])
        
        df = df.with_columns(
            (pl.col(f"{column}_macd") - pl.col(f"{column}_macd_signal")).alias(f"{column}_macd_hist")
        )
        
        return df.drop("macd_line_temp")

    @staticmethod
    def add_time_features(df: pl.DataFrame) -> pl.DataFrame:
        """
        Extracts day, hour, and financial trading sessions (London, NY, Tokyo).
        """
        return df.with_columns([
            pl.col("timestamp").dt.hour().alias("hour"),
            pl.col("timestamp").dt.weekday().alias("day_of_week"),
            # Sessions check (in UTC time)
            # London: 08:00 to 16:30 UTC
            pl.when((pl.col("timestamp").dt.hour() >= 8) & (pl.col("timestamp").dt.hour() < 17))
            .then(1).otherwise(0).alias("is_london_session"),
            # New York: 13:00 to 21:00 UTC
            pl.when((pl.col("timestamp").dt.hour() >= 13) & (pl.col("timestamp").dt.hour() < 22))
            .then(1).otherwise(0).alias("is_ny_session"),
            # Tokyo: 00:00 to 09:00 UTC
            pl.when((pl.col("timestamp").dt.hour() >= 0) & (pl.col("timestamp").dt.hour() < 9))
            .then(1).otherwise(0).alias("is_tokyo_session")
        ])

    @staticmethod
    def compute_garman_klass_volatility(df: pl.DataFrame, period: int = 30) -> pl.DataFrame:
        """
        Computes Garman-Klass historical volatility estimator.
        """
        log_hl = (pl.col("high") / pl.col("low")).log()
        log_co = (pl.col("close") / pl.col("open")).log()
        
        gk_element = 0.5 * (log_hl ** 2) - (2 * np.log(2) - 1) * (log_co ** 2)
        gk_vol = gk_element.rolling_mean(window_size=period).sqrt()
        
        return df.with_columns(gk_vol.alias(f"gk_vol_{period}"))

    @staticmethod
    def compute_all_features(df: pl.DataFrame) -> pl.DataFrame:
        """
        Runs the complete feature engineering pipeline on input candles.
        """
        # Ensure df is sorted by timestamp
        df = df.sort("timestamp")
        
        df = FeatureCalculator.compute_sma(df, "close", 10)
        df = FeatureCalculator.compute_sma(df, "close", 50)
        df = FeatureCalculator.compute_ema(df, "close", 20)
        df = FeatureCalculator.compute_rsi(df, "close", 14)
        df = FeatureCalculator.compute_atr(df, 14)
        df = FeatureCalculator.compute_bollinger_bands(df, "close", 20)
        df = FeatureCalculator.compute_macd(df, "close")
        df = FeatureCalculator.add_time_features(df)
        df = FeatureCalculator.compute_garman_klass_volatility(df, 14)
        
        # Calculate target label for training (e.g. forward returns over next 5 periods)
        df = df.with_columns(
            ((pl.col("close").shift(-5) - pl.col("close")) / pl.col("close")).alias("target_return_5p")
        )
        
        # Forward classification label (1 = up, 0 = down)
        df = df.with_columns(
            pl.when(pl.col("target_return_5p") > 0.0005).then(1)
            .when(pl.col("target_return_5p") < -0.0005).then(-1)
            .otherwise(0).alias("target_direction_5p")
        )
        
        return df.interpolate()
