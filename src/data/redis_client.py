import json
import logging
import collections
from typing import List, Dict, Any, Optional
import redis
from src.config import load_config

logger = logging.getLogger("RedisClient")

class RedisClient:
    """
    High-performance client for caching live ticks and candles.
    Gracefully falls back to thread-safe in-memory deques if Redis is offline.
    """
    def __init__(self):
        cfg = load_config()
        self.host = cfg.redis.host
        self.port = cfg.redis.port
        self.db_num = cfg.redis.db
        self.r = None
        self.offline_mode = False
        
        # In-memory fallbacks
        self._memory_ticks: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=3600))
        self._memory_candles: Dict[str, collections.deque] = collections.defaultdict(lambda: collections.deque(maxlen=1000))

        try:
            self.r = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db_num,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
                decode_responses=True
            )
            # Ping test
            self.r.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            self.offline_mode = True
            logger.warning(f"Could not connect to Redis: {e}. Falling back to in-memory caching.")

    def store_tick(self, symbol: str, tick_data: Dict[str, Any], max_len: int = 3600) -> bool:
        """
        Stores a tick data dict. Returns True if succeeded.
        """
        # Serialize datetime keys to isoformat
        serialized = {}
        for k, v in tick_data.items():
            if hasattr(v, 'isoformat'):
                serialized[k] = v.isoformat()
            else:
                serialized[k] = v

        if self.offline_mode or not self.r:
            self._memory_ticks[symbol].append(serialized)
            return True

        try:
            key = f"ticks:{symbol}"
            self.r.rpush(key, json.dumps(serialized))
            self.r.ltrim(key, -max_len, -1)
            # Expire tick list in 2 hours to avoid orphan memory buildup
            self.r.expire(key, 7200)
            return True
        except Exception as e:
            logger.debug(f"Redis write error, caching in memory: {e}")
            self._memory_ticks[symbol].append(serialized)
            return True

    def get_recent_ticks(self, symbol: str, count: int = 100) -> List[Dict[str, Any]]:
        """
        Returns recent ticks.
        """
        if self.offline_mode or not self.r:
            dq = self._memory_ticks[symbol]
            return list(dq)[-count:]

        try:
            key = f"ticks:{symbol}"
            raw_ticks = self.r.lrange(key, -count, -1)
            return [json.loads(t) for t in raw_ticks]
        except Exception as e:
            logger.debug(f"Redis read error, reading from memory cache: {e}")
            dq = self._memory_ticks[symbol]
            return list(dq)[-count:]

    def store_candle(self, symbol: str, timeframe: str, candle_data: Dict[str, Any], max_len: int = 1000) -> bool:
        """
        Stores a candle data dict.
        """
        serialized = {}
        for k, v in candle_data.items():
            if hasattr(v, 'isoformat'):
                serialized[k] = v.isoformat()
            else:
                serialized[k] = v

        if self.offline_mode or not self.r:
            self._memory_candles[f"{symbol}:{timeframe}"].append(serialized)
            return True

        try:
            key = f"candles:{symbol}:{timeframe}"
            self.r.rpush(key, json.dumps(serialized))
            self.r.ltrim(key, -max_len, -1)
            self.r.expire(key, 86400) # Expire in 1 day
            return True
        except Exception as e:
            logger.debug(f"Redis write error, caching in memory: {e}")
            self._memory_candles[f"{symbol}:{timeframe}"].append(serialized)
            return True

    def get_recent_candles(self, symbol: str, timeframe: str, count: int = 100) -> List[Dict[str, Any]]:
        """
        Returns recent candles.
        """
        if self.offline_mode or not self.r:
            dq = self._memory_candles[f"{symbol}:{timeframe}"]
            return list(dq)[-count:]

        try:
            key = f"candles:{symbol}:{timeframe}"
            raw_candles = self.r.lrange(key, -count, -1)
            return [json.loads(c) for c in raw_candles]
        except Exception as e:
            logger.debug(f"Redis read error, reading from memory: {e}")
            dq = self._memory_candles[f"{symbol}:{timeframe}"]
            return list(dq)[-count:]
