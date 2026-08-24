import asyncio
from collections import deque
from logging import Logger
import time

from common.logging.global_logger import get_global_logger

logger: Logger = get_global_logger(__name__)

class RateLimiter:
    def __init__(self, max_rate: int, time_window: float):
        self.max_rate: int = max_rate
        self.current_value: int = 0
        self.time_window: float = time_window
        self.history: deque[tuple[float, int]] = deque()
        self.lock = asyncio.Lock() # This lock is used to ensure that only one coroutine can modify the rate limiter's state at a time, preventing race conditions in a concurrent environment.
        logger.info(f'RateLimiter initialized with max_rate: {self.max_rate}, time_window: {self.time_window} seconds')

    def _remove_expired(self, now: float):
        removed: int = 0
        while self.history and now - self.history[0][0] >= self.time_window:
            removed += 1
            timestamp, value = self.history.popleft()
            self.current_value -= value
            logger.debug(f'Expired entry removed. Timestamp: {timestamp}, Value: {value}, Current value: {self.current_value}')
        logger.info(f'Total expired entries removed: {removed}. Current value after cleanup: {self.current_value}')

    def _time_until_available(self, now: float, value: int) -> float:
        total_value = self.current_value + value
        if total_value <= self.max_rate:
            logger.error('This method should only be called when the requested value exceeds the max rate.')
            raise RuntimeError('This method should only be called when the requested value exceeds the max rate.')

        for i in range(len(self.history)):
            total_value -= self.history[i][1]
            if total_value <= self.max_rate:
                earliest_time = self.history[i][0]
                time_until_available = (earliest_time + self.time_window) - now
                logger.info(f'Rate limit will be free after processing entry at index {i} (timestamp: {self.history[i][0]}, value: {self.history[i][1]}), time until available: {time_until_available} seconds')
                return max(time_until_available, 0.0)
            logger.debug(f'Entry at index {i} (timestamp: {self.history[i][0]}, value: {self.history[i][1]}) does not free up enough capacity. Total value after this entry: {total_value}, max rate: {self.max_rate}')

        logger.error('Unreachable state reached in _time_until_available method.')
        raise RuntimeError('Unreachable state reached in _time_until_available method.')

    async def acquire(self, value: int = 1):
        if value > self.max_rate:
            logger.error(f'Requested value {value} exceeds the limiter capacity of {self.max_rate}.')
            raise ValueError('Requested value exceeds limiter capacity.')

        while True:
            async with self.lock:
                now: float = time.monotonic()
                self._remove_expired(now)
                if self.current_value + value <= self.max_rate:
                    self.current_value += value
                    self.history.append((now, value))
                    logger.info(f'Rate limit acquired for value {value}. Current value: {self.current_value}')
                    return

                wait: float = self._time_until_available(now, value)

                # Lock released while sleeping
                await asyncio.sleep(wait)
                logger.info(f'Rate limit acquisition for value {value} completed after waiting for {wait} seconds.')
