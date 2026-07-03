import datetime
import random
import logging
from sqlalchemy.orm import Session
from src.data.database import MarketData, MacroEvent, NewsSentiment
from src.data.validator import DataValidator

logger = logging.getLogger("DataCollector")

class DataCollector:
    """
    Ingests and normalizes market data, macroeconomic events, and news sentiment feeds.
    Provides methods to persist validated data into the database.
    """
    def __init__(self, db: Session):
        self.db = db

    def ingest_market_candle(self, timestamp: datetime.datetime, symbol: str, timeframe: str,
                            open_p: float, high_p: float, low_p: float, close_p: float,
                            volume: float, bid_p: float, ask_p: float) -> bool:
        """
        Validates and commits a single price candle.
        """
        raw_data = {
            "timestamp": timestamp,
            "symbol": symbol,
            "timeframe": timeframe,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": volume,
            "bid": bid_p,
            "ask": ask_p
        }

        if not DataValidator.validate_market_data(raw_data):
            logger.warning(f"Discarding invalid market data for {symbol} at {timestamp}")
            return False

        try:
            # Check if candle already exists
            existing = self.db.query(MarketData).filter_by(
                symbol=symbol, timeframe=timeframe, timestamp=timestamp
            ).first()
            
            if existing:
                existing.open = open_p
                existing.high = high_p
                existing.low = low_p
                existing.close = close_p
                existing.volume = volume
                existing.bid = bid_p
                existing.ask = ask_p
            else:
                candle = MarketData(**raw_data)
                self.db.add(candle)
                
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to persist market candle: {e}")
            return False

    def ingest_macro_event(self, timestamp: datetime.datetime, event_name: str, country: str,
                           actual: float | None, forecast: float | None, previous: float | None,
                           importance: str) -> bool:
        """
        Validates and commits a macroeconomic calendar event.
        """
        raw_data = {
            "timestamp": timestamp,
            "event_name": event_name,
            "country": country,
            "actual": actual,
            "forecast": forecast,
            "previous": previous,
            "importance": importance
        }

        if not DataValidator.validate_macro_event(raw_data):
            logger.warning(f"Discarding invalid macro event: {event_name} at {timestamp}")
            return False

        try:
            # Check for duplication using event name and timestamp
            existing = self.db.query(MacroEvent).filter_by(
                event_name=event_name, timestamp=timestamp
            ).first()

            if not existing:
                event = MacroEvent(**raw_data)
                self.db.add(event)
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to persist macro event: {e}")
            return False

    def ingest_news_sentiment(self, timestamp: datetime.datetime, source: str, title: str,
                              sentiment_score: float, embedding: list[float] | None = None) -> bool:
        """
        Validates and commits a news sentiment data point.
        """
        raw_data = {
            "timestamp": timestamp,
            "source": source,
            "title": title,
            "sentiment_score": sentiment_score,
            "sentiment_embedding": embedding
        }

        if not DataValidator.validate_news_sentiment(raw_data):
            logger.warning(f"Discarding invalid news sentiment score for '{title}' at {timestamp}")
            return False

        try:
            news = NewsSentiment(**raw_data)
            self.db.add(news)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to persist news sentiment: {e}")
            return False

    def generate_mock_market_tick(self, base_price: float = 2330.00) -> dict:
        """
        Generates realistic random walk ticks representing Gold spread and bid-ask.
        Useful for running simulations and dashboard streaming.
        """
        change = random.normalvariate(0.0, 0.5)
        last_price = base_price + change
        spread = round(random.uniform(0.12, 0.25), 2)  # Tight institutional spreads (1.2 to 2.5 pips)
        bid = round(last_price - spread / 2, 2)
        ask = round(last_price + spread / 2, 2)
        return {
            "timestamp": datetime.datetime.now(datetime.timezone.utc),
            "symbol": "XAUUSD",
            "timeframe": "tick",
            "open": last_price,
            "high": max(bid, ask),
            "low": min(bid, ask),
            "close": last_price,
            "volume": round(random.uniform(10, 150), 2),
            "bid": bid,
            "ask": ask
        }
