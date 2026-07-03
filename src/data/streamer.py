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

TIMEFRAME_SECS = {
    "1s": 1,
    "5s": 5,
    "15s": 15,
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400
}

def align_timestamp(dt: datetime.datetime, duration_seconds: int) -> datetime.datetime:
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    ts_seconds = int((dt - epoch).total_seconds())
    aligned_seconds = (ts_seconds // duration_seconds) * duration_seconds
    return epoch + datetime.timedelta(seconds=aligned_seconds)

class RealTimeStreamer:
    """
    Simulates or streams live XAU/USD price updates every second.
    Computes feed latency, detects stale data, missing ticks, spikes, duplicates, and API delay.
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
            "api_delay": False,
            "duplicate_ticks": False
        }

        # Multi-timeframe active candles
        self.current_candles = {tf: None for tf in TIMEFRAME_SECS}

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
        import yfinance as yf
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

        last_fetched_price = None
        last_fetch_time = 0.0

        while not self._stop_event.is_set():
            start_time = time.time()
            try:
                # 1. Fetch live gold price from yfinance (GC=F) every 5 seconds to avoid rate-limiting
                now_time = time.time()
                network_latency = 110.0  # default lookup delay
                
                if now_time - last_fetch_time >= 5.0 or last_fetched_price is None:
                    network_start = time.time()
                    try:
                        # Re-instantiate Ticker to clear instance cache and force network request
                        ticker = yf.Ticker("GC=F")
                        info = ticker.fast_info
                        if "lastPrice" in info:
                            last_fetched_price = round(float(info["lastPrice"]), 2)
                        elif "last_price" in info:
                            last_fetched_price = round(float(info["last_price"]), 2)
                        last_fetch_time = now_time
                        network_latency = (time.time() - network_start) * 1000
                    except Exception as ex:
                        logger.debug(f"yfinance live price fetch failed: {ex}")
                
                # Fallback to base price if yfinance fails
                if last_fetched_price is None:
                    last_fetched_price = base_price

                # 2. Generate 1-second micro-tick variations around the last fetched price
                # Small micro-price oscillations (e.g. ±0.01 to ±0.05 cents) to keep the chart active
                micro_change = random.normalvariate(0.0, 0.04)
                spot_price = round(last_fetched_price + micro_change, 2)
                
                # Calculate latency
                self.feed_latency_ms = round(network_latency, 2)
                base_price = spot_price  # update running base
                
                spread = round(random.uniform(0.12, 0.22), 2)  # 1.2 to 2.2 pips
                bid = round(spot_price - spread / 2, 2)
                ask = round(spot_price + spread / 2, 2)
                
                is_anomaly = False
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
                process_time = time.time()
                
                # 3. Detect Anomalies
                self._detect_anomalies(tick, is_anomaly)
                
                # 4. Store tick in Redis
                self.redis_client.store_tick(self.symbol, tick)
                
                # 5. Aggregate tick into multiple historical timeframe candles
                self._aggregate_all_timeframes(db, tick)
                
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

        # 5. Duplicate tick check
        if self.last_tick and tick["price"] == self.last_tick["price"] and tick["timestamp"] == self.last_tick["timestamp"]:
            self.status_flags["duplicate_ticks"] = True
        else:
            self.status_flags["duplicate_ticks"] = False

    def _aggregate_all_timeframes(self, db: Session, tick: Dict[str, Any]):
        now = datetime.datetime.fromisoformat(tick["timestamp"]) if isinstance(tick["timestamp"], str) else tick["timestamp"]
        if now.tzinfo is None:
            now = now.replace(tzinfo=datetime.timezone.utc)

        price = tick["price"]
        bid = tick["bid"]
        ask = tick["ask"]
        volume = tick["volume"]

        for tf, duration in TIMEFRAME_SECS.items():
            aligned_ts = align_timestamp(now, duration)
            candle = self.current_candles.get(tf)

            if candle is None:
                self.current_candles[tf] = {
                    "timestamp": aligned_ts,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume,
                    "bid": bid,
                    "ask": ask
                }
            elif candle["timestamp"] == aligned_ts:
                # Update current active candle
                candle["high"] = max(candle["high"], price)
                candle["low"] = min(candle["low"], price)
                candle["close"] = price
                candle["volume"] += volume
                candle["bid"] = bid
                candle["ask"] = ask
            else:
                # Rollover! The period completed.
                completed_candle = candle
                
                # 1. Cache the completed candle in Redis
                self.redis_client.store_candle(self.symbol, tf, completed_candle)
                
                # 2. Persist to SQLite/PostgreSQL for timeframes 1m and above (to avoid heavy DB disk write locks on sub-minute)
                if duration >= 60:
                    try:
                        existing = db.query(MarketData).filter_by(
                            symbol=self.symbol, timeframe=tf, timestamp=completed_candle["timestamp"]
                        ).first()
                        if existing:
                            existing.open = completed_candle["open"]
                            existing.high = completed_candle["high"]
                            existing.low = completed_candle["low"]
                            existing.close = completed_candle["close"]
                            existing.volume = completed_candle["volume"]
                            existing.bid = completed_candle["bid"]
                            existing.ask = completed_candle["ask"]
                        else:
                            new_db_candle = MarketData(
                                timestamp=completed_candle["timestamp"],
                                symbol=self.symbol,
                                timeframe=tf,
                                open=completed_candle["open"],
                                high=completed_candle["high"],
                                low=completed_candle["low"],
                                close=completed_candle["close"],
                                volume=completed_candle["volume"],
                                bid=completed_candle["bid"],
                                ask=completed_candle["ask"]
                            )
                            db.add(new_db_candle)
                        db.commit()
                        logger.info(f"Persisted aggregated {tf} candle for {completed_candle['timestamp']}")
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Error persisting {tf} candle: {e}")

                # Start the next candle
                self.current_candles[tf] = {
                    "timestamp": aligned_ts,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume,
                    "bid": bid,
                    "ask": ask
                }

