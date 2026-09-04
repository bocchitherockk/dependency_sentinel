import asyncio
from collections import deque
from logging import Logger
import time


class RateLimiter:
    def __init__(self, max_rate: int, time_window: float):
        self.max_rate: int = max_rate
        self.current_value: int = 0
        self.time_window: float = time_window
        self.history: deque[tuple[float, int]] = deque()
        self.lock = asyncio.Lock() # This lock is used to ensure that only one coroutine can modify the rate limiter's state at a time, preventing race conditions in a concurrent environment.
        print(f'RateLimiter initialized with max_rate: {self.max_rate}, time_window: {self.time_window} seconds')

    def _remove_expired(self, now: float):
        removed: int = 0
        while self.history and now - self.history[0][0] >= self.time_window:
            removed += 1
            timestamp, value = self.history.popleft()
            self.current_value -= value
            print(f'Expired entry removed. Timestamp: {timestamp}, Value: {value}, Current value: {self.current_value}')
        print(f'Total expired entries removed: {removed}. Current value after cleanup: {self.current_value}')

    def _time_until_available(self, now: float, value: int) -> float:
        total_value = self.current_value + value
        if total_value <= self.max_rate:
            print('This method should only be called when the requested value exceeds the max rate.')
            raise RuntimeError('This method should only be called when the requested value exceeds the max rate.')

        for i in range(len(self.history)):
            total_value -= self.history[i][1]
            if total_value <= self.max_rate:
                earliest_time = self.history[i][0]
                time_until_available = (earliest_time + self.time_window) - now
                print(f'Rate limit will be free after processing entry at index {i} (timestamp: {self.history[i][0]}, value: {self.history[i][1]}), time until available: {time_until_available} seconds')
                return max(time_until_available, 0.0)
            print(f'Entry at index {i} (timestamp: {self.history[i][0]}, value: {self.history[i][1]}) does not free up enough capacity. Total value after this entry: {total_value}, max rate: {self.max_rate}')

        print('Unreachable state reached in _time_until_available method.')
        raise RuntimeError('Unreachable state reached in _time_until_available method.')

    async def acquire(self, value: int = 1):
        if value > self.max_rate:
            print(f'Requested value {value} exceeds the limiter capacity of {self.max_rate}.')
            raise ValueError('Requested value exceeds limiter capacity.')

        while True:
            async with self.lock:
                now: float = time.monotonic()
                self._remove_expired(now)
                if self.current_value + value <= self.max_rate:
                    self.current_value += value
                    self.history.append((now, value))
                    print(f'Rate limit acquired for value {value}. Current value: {self.current_value}')
                    return

                wait: float = self._time_until_available(now, value)
                print(f'Rate limit not available for value {value}. Need to wait for {wait} seconds before retrying.')

            # Lock released while sleeping
            await asyncio.sleep(wait)


async def main():
    rate_limiter = RateLimiter(max_rate=5, time_window=10.0)  # Example: max 5 requests per 10 seconds

    async def make_request(request_id: int):
        await rate_limiter.acquire()
        print(f'Request {request_id} is being processed.')

    tasks = [make_request(i) for i in range(11)]  # Simulate 10 requests
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
