import time
import datetime
import random
import logging
import threading
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.data.redis_client import RedisClient
from src.data.database import SessionLocal, MarketData

logger = logging.getLogger("RealTimeStreamer")

class RealTimeStreamer:
    """
    Simulates or streams live XAU/USD price updates every second.
    Computes feed latency, detects stale data, missing ticks, and abnormal spikes.
    Caches ticks/candles in Redis and aggregates historical candles in SQLite/PostgreSQL.
    """
    def __init__(self, symbol: str = "XAUUSD"):
        self.symbol = symbol
        self.redis_client = RedisClient()
        
        # State tracking
        self.last_tick: Optional[Dict[str, Any]] = None
        self.last_tick_time: float = 0.0
        self.tick_count: int = 0
        self.consecutive_missing: int = 0
        
        # Statistical helpers for spike detection
        self.price_window = []
        self.window_max_len = 30
        
        # Controls
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # Telemetry metrics
        self.feed_latency_ms: float = 0.0
        self.status_flags = {
            "stale": False,
            "missing_ticks": False,
            "abnormal_spike": False,
            "api_delay": False
        }

    def start(self):
        """Starts the real-time streaming thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="GoldStreamerThread")
        self._thread.start()
        logger.info("Real-Time Streaming Engine started.")

    def stop(self):
        """Stops the streaming thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Real-Time Streaming Engine stopped.")

    def _run_loop(self):
        base_price = 2330.00
        db = SessionLocal()
        
        # Warmup base price from DB if available
        try:
            latest = db.query(MarketData).filter_by(symbol=self.symbol).order_by(MarketData.timestamp.desc()).first()
            if latest:
                base_price = float(latest.close)
                logger.info(f"Streamer warmed up with base price ${base_price:.2f} from database.")
        except Exception as e:
            logger.error(f"Warmup price query failed: {e}")

        while not self._stop_event.is_set():
            start_time = time.time()
            try:
                # 1. Simulate tick update (or poll if API was WebSocket-enabled)
                # Gold price random walk
                change = random.normalvariate(0.0, 0.12)
                # Keep gold price moves small & realistic for 1-second ticks
                spot_price = round(base_price + change, 2)
                base_price = spot_price  # update running base
                
                spread = round(random.uniform(0.12, 0.22), 2)  # 1.2 to 2.2 pips
                bid = round(spot_price - spread / 2, 2)
                ask = round(spot_price + spread / 2, 2)
                
                # Check for artificial spikes sometimes for testing
                is_anomaly = False
                if random.random() < 0.005:  # 0.5% chance to create spike
                    spot_price = round(spot_price * (1.0 + random.choice([-0.015, 0.015])), 2)
                    bid = round(spot_price - spread / 2, 2)
                    ask = round(spot_price + spread / 2, 2)
                    is_anomaly = True
                    logger.warning(f"Artificially injected price spike: ${spot_price}")

                now = datetime.datetime.now(datetime.timezone.utc)
                
                tick = {
                    "timestamp": now.isoformat(),
                    "symbol": self.symbol,
                    "price": spot_price,
                    "bid": bid,
                    "ask": ask,
                    "spread": spread,
                    "volume": round(random.uniform(5.0, 50.0), 2)
                }

                # 2. Compute Latency
                # Time diff between tick generation and current processing time
                process_time = time.time()
                # Simulate network network delay (80ms to 150ms)
                simulated_network_delay = random.uniform(0.08, 0.15)
                self.feed_latency_ms = round(simulated_network_delay * 1000, 2)
                
                # 3. Detect Anomalies
                self._detect_anomalies(tick, is_anomaly)
                
                # 4. Store tick in Redis
                self.redis_client.store_tick(self.symbol, tick)
                
                # 5. Aggregate tick into 1-minute historical candles in DB
                self._aggregate_candle_to_db(db, tick)
                
                self.last_tick = tick
                self.last_tick_time = process_time
                self.tick_count += 1
                
            except Exception as e:
                logger.error(f"Error in streamer loop: {e}")
                
            # Sleep to match exactly 1s frequency
            elapsed = time.time() - start_time
            sleep_time = max(0.0, 1.0 - elapsed)
            time.sleep(sleep_time)
            
        db.close()

    def _detect_anomalies(self, tick: Dict[str, Any], is_anomaly: bool):
        price = tick["price"]
        now_time = time.time()
        
        # 1. Stale feed check
        if self.last_tick_time > 0 and (now_time - self.last_tick_time) > 3.0:
            self.status_flags["stale"] = True
            logger.warning("Feed is stale! No updates for > 3 seconds.")
        else:
            self.status_flags["stale"] = False
            
        # 2. Missing ticks check (expected 1 tick per second)
        if self.last_tick_time > 0:
            actual_gap = now_time - self.last_tick_time
            if actual_gap > 1.8:
                self.consecutive_missing += int(actual_gap) - 1
                self.status_flags["missing_ticks"] = True
                logger.warning(f"Missing tick detected. Consecutive missing ticks: {self.consecutive_missing}")
            else:
                self.consecutive_missing = 0
                self.status_flags["missing_ticks"] = False

        # 3. Spike detection
        self.price_window.append(price)
        if len(self.price_window) > self.window_max_len:
            self.price_window.pop(0)
            
        if len(self.price_window) >= 10:
            mean = sum(self.price_window) / len(self.price_window)
            variance = sum((x - mean) ** 2 for x in self.price_window) / len(self.price_window)
            std_dev = variance ** 0.5
            
            # Spike defined as deviation > 3 standard deviations and absolute difference > 0.3%
            if std_dev > 0 and abs(price - mean) > (3 * std_dev) and (abs(price - mean) / mean) > 0.003:
                self.status_flags["abnormal_spike"] = True
                logger.warning(f"Abnormal price spike detected: Price ${price} deviates from rolling mean ${mean:.2f} (std_dev: {std_dev:.4f})")
            else:
                self.status_flags["abnormal_spike"] = False
        else:
            self.status_flags["abnormal_spike"] = False

        # If manually injected spike, override to True
        if is_anomaly:
            self.status_flags["abnormal_spike"] = True

        # 4. API Delay check
        if self.feed_latency_ms > 300.0:
            self.status_flags["api_delay"] = True
        else:
            self.status_flags["api_delay"] = False

    def _aggregate_candle_to_db(self, db: Session, tick: Dict[str, Any]):
        """
        Aggregates tick price into the current minute candle in SQLite/PostgreSQL.
        Writes and commits to the database only on minute rollover to prevent SQLite locks.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        minute_ts = now.replace(second=0, microsecond=0)
        price = tick["price"]
        bid = tick["bid"]
        ask = tick["ask"]
        volume = tick["volume"]

        if not hasattr(self, 'current_candle'):
            self.current_candle = None

        if self.current_candle is None:
            self.current_candle = {
                "timestamp": minute_ts,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "bid": bid,
                "ask": ask
            }
        elif self.current_candle["timestamp"] == minute_ts:
            self.current_candle["high"] = max(self.current_candle["high"], price)
            self.current_candle["low"] = min(self.current_candle["low"], price)
            self.current_candle["close"] = price
            self.current_candle["volume"] += volume
            self.current_candle["bid"] = bid
            self.current_candle["ask"] = ask
        else:
            # Minute rolled over! Write completed candle to DB
            completed = self.current_candle
            try:
                existing = db.query(MarketData).filter_by(
                    symbol=self.symbol, timeframe="1m", timestamp=completed["timestamp"]
                ).first()
                if existing:
                    existing.high = completed["high"]
                    existing.low = completed["low"]
                    existing.close = completed["close"]
                    existing.volume = completed["volume"]
                    existing.bid = completed["bid"]
                    existing.ask = completed["ask"]
                else:
                    candle = MarketData(
                        timestamp=completed["timestamp"],
                        symbol=self.symbol,
                        timeframe="1m",
                        open=completed["open"],
                        high=completed["high"],
                        low=completed["low"],
                        close=completed["close"],
                        volume=completed["volume"],
                        bid=completed["bid"],
                        ask=completed["ask"]
                    )
                    db.add(candle)
                db.commit()
                logger.info(f"Aggregated 1-minute candle committed to DB for {completed['timestamp']}")
            except Exception as e:
                db.rollback()
                logger.error(f"Error persisting aggregated candle on rollover: {e}")
            
            # Start new candle
            self.current_candle = {
                "timestamp": minute_ts,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "bid": bid,
                "ask": ask
            }

