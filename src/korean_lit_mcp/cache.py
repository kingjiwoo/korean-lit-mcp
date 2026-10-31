"""Bounded process-local cache for public upstream bytes, never teacher inputs."""

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    expires: float
    value: bytes


class CacheBusy(Exception):
    pass


class PublicCache:
    def __init__(
        self,
        *,
        max_entries: int = 256,
        max_bytes: int = 8 * 1024 * 1024,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1 or max_bytes < 1:
            raise ValueError("Cache limits must be positive.")
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.clock = clock
        self.entries: OrderedDict[tuple[str, ...], Entry] = OrderedDict()
        self.pending: dict[tuple[str, ...], asyncio.Task[bytes]] = {}
        self.bytes_used = 0

    async def get(
        self,
        key: tuple[str, ...],
        fetch: Callable[[], Awaitable[bytes]],
        *,
        ttl: float | Callable[[bytes], float],
    ) -> bytes:
        if not callable(ttl) and ttl < 0:
            raise ValueError("TTL must not be negative.")
        entry = self.entries.get(key)
        if entry is not None:
            if entry.expires > self.clock():
                self.entries.move_to_end(key)
                logging.getLogger(__name__).info("cache event=hit")
                return entry.value
            self.bytes_used -= len(self.entries.pop(key).value)
        task = self.pending.get(key)
        if task is None:
            if len(self.pending) >= 16:
                raise CacheBusy("Upstream concurrency limit reached.")
            task = asyncio.create_task(self._fetch(key, fetch, ttl))
            logging.getLogger(__name__).info("cache event=fetch")
            self.pending[key] = task
            # Retrieve errors even if every waiting request has been cancelled.
            task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        return await asyncio.shield(task)

    async def _fetch(
        self,
        key: tuple[str, ...],
        fetch: Callable[[], Awaitable[bytes]],
        ttl: float | Callable[[bytes], float],
    ) -> bytes:
        try:
            async with asyncio.timeout(15):
                value = await fetch()
            lifetime = ttl(value) if callable(ttl) else ttl
            if lifetime < 0:
                raise ValueError("TTL must not be negative.")
            if lifetime > 0 and len(value) <= self.max_bytes:
                while self.entries and (
                    len(self.entries) >= self.max_entries
                    or self.bytes_used + len(value) > self.max_bytes
                ):
                    _, removed = self.entries.popitem(last=False)
                    logging.getLogger(__name__).info("cache event=evict")
                    self.bytes_used -= len(removed.value)
                self.entries[key] = Entry(self.clock() + lifetime, value)
                self.bytes_used += len(value)
            return value
        finally:
            self.pending.pop(key, None)
