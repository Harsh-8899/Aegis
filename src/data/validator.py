import datetime
import logging
from typing import Dict, Any, Union
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("DataValidator")

class MarketDataValidationSchema(BaseModel):
    timestamp: datetime.datetime
    symbol: str = Field(..., max_length=12)
    timeframe: str = Field(..., max_length=4)
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: float = Field(..., ge=0)
    bid: float = Field(..., gt=0)
    ask: float = Field(..., gt=0)

    @field_validator("ask")
    @classmethod
    def validate_spread(cls, ask_val: float, info) -> float:
        bid_val = info.data.get("bid")
        if bid_val is not None and ask_val < bid_val:
            raise ValueError(f"Ask price ({ask_val}) must be greater than or equal to Bid price ({bid_val})")
        return ask_val

    @field_validator("high")
    @classmethod
    def validate_high_low(cls, high_val: float, info) -> float:
        low_val = info.data.get("low")
        open_val = info.data.get("open")
        close_val = info.data.get("close")
        
        if low_val is not None and high_val < low_val:
            raise ValueError(f"High price ({high_val}) cannot be lower than Low price ({low_val})")
            
        for price_name, price_val in [("Open", open_val), ("Close", close_val)]:
            if price_val is not None and high_val < price_val:
                raise ValueError(f"High price ({high_val}) cannot be lower than {price_name} price ({price_val})")
                
        return high_val

class MacroEventValidationSchema(BaseModel):
    timestamp: datetime.datetime
    event_name: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=2, max_length=10)
    actual: float | None = None
    forecast: float | None = None
    previous: float | None = None
    importance: str = Field(..., pattern="^(HIGH|MEDIUM|LOW)$")

class NewsSentimentValidationSchema(BaseModel):
    timestamp: datetime.datetime
    source: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1)
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)

class DataValidator:
    @staticmethod
    def validate_market_data(data: Dict[str, Any]) -> bool:
        try:
            MarketDataValidationSchema(**data)
            return True
        except Exception as e:
            logger.error(f"Market data validation failed for {data}: {e}")
            return False

    @staticmethod
    def validate_macro_event(data: Dict[str, Any]) -> bool:
        try:
            MacroEventValidationSchema(**data)
            return True
        except Exception as e:
            logger.error(f"Macro event validation failed for {data}: {e}")
            return False

    @staticmethod
    def validate_news_sentiment(data: Dict[str, Any]) -> bool:
        try:
            NewsSentimentValidationSchema(**data)
            return True
        except Exception as e:
            logger.error(f"News sentiment validation failed for {data}: {e}")
            return False
