import polars as pl
import pandas as pd
from sqlalchemy.orm import Session
from src.data.database import MarketData
from src.features.calculations import FeatureCalculator

class FeatureStore:
    """
    Interfaces with the database to load prices, run the feature engineering pipeline,
    and serve feature vectors for ML model training and inference.
    """
    def __init__(self, db: Session):
        self.db = db

    def load_candles_as_dataframe(self, symbol: str = "XAUUSD", timeframe: str = "1m", limit: int = 2000) -> pl.DataFrame:
        """
        Loads candles from the database and returns a sorted Polars DataFrame.
        """
        query = (
            self.db.query(MarketData)
            .filter_by(symbol=symbol, timeframe=timeframe)
            .order_by(MarketData.timestamp.asc())
        )
        
        if limit:
            # Get latest limit candles but preserve chronological order
            subquery = query.order_by(MarketData.timestamp.desc()).limit(limit).subquery()
            query = self.db.query(subquery).order_by(subquery.c.timestamp.asc())

        # Read into pandas first as SQLAlchemy to polars directly is easiest via pandas/dict
        records = [
            {
                "timestamp": r.timestamp,
                "open": float(r.open) if r.open else 0.0,
                "high": float(r.high) if r.high else 0.0,
                "low": float(r.low) if r.low else 0.0,
                "close": float(r.close) if r.close else 0.0,
                "volume": float(r.volume) if r.volume else 0.0,
                "bid": float(r.bid) if r.bid else 0.0,
                "ask": float(r.ask) if r.ask else 0.0,
            }
            for r in query.all()
        ]
        
        if not records:
            return pl.DataFrame()
            
        return pl.DataFrame(records)

    def get_features(self, symbol: str = "XAUUSD", timeframe: str = "1m", limit: int = 2000) -> pl.DataFrame:
        """
        Loads market data and computes technical and statistical features.
        """
        df = self.load_candles_as_dataframe(symbol, timeframe, limit)
        if df.is_empty():
            return df
        return FeatureCalculator.compute_all_features(df)

    def get_latest_feature_vector(self, symbol: str = "XAUUSD", timeframe: str = "1m") -> dict | None:
        """
        Returns the single latest feature row as a dictionary for live inference.
        """
        # Load slightly more than 100 periods to ensure indicator warmups (e.g. SMA 50, EMA 20, BB 20) are fully calculated
        df = self.get_features(symbol, timeframe, limit=150)
        if df.is_empty():
            return None
        
        # Get the absolute last row (which represents the most recently completed bar)
        latest_row = df.tail(1).to_dicts()
        return latest_row[0] if latest_row else None
