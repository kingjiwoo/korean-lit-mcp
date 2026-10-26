import asyncio

import pytest

from korean_lit_mcp.cache import CacheBusy, PublicCache


async def test_ttl_and_retrieval() -> None:
    now = [0.0]
    cache = PublicCache(clock=lambda: now[0])
    calls = 0

    async def fetch() -> bytes:
        nonlocal calls
        calls += 1
        return b"public-data"

    assert await cache.get(("source", "q"), fetch, ttl=10) == b"public-data"
    await cache.get(("source", "q"), fetch, ttl=10)
    assert calls == 1
    now[0] = 10
    await cache.get(("source", "q"), fetch, ttl=10)
    assert calls == 2


async def test_lru_byte_and_entry_limits() -> None:
    cache = PublicCache(max_entries=2, max_bytes=4)

    async def small() -> bytes:
        return b"ab"

    async def large() -> bytes:
        return b"abcde"

    for key in ("a", "b", "a", "c"):
        await cache.get((key,), small, ttl=10)
    assert list(cache.entries) == [("a",), ("c",)]
    assert cache.bytes_used == 4
    await cache.get(("large",), large, ttl=10)
    assert ("large",) not in cache.entries
    assert cache.bytes_used == 4


async def test_concurrent_waiter_cancellation_does_not_cancel_fetch() -> None:
    cache = PublicCache()
    started, finish = asyncio.Event(), asyncio.Event()
    calls = 0

    async def fetch() -> bytes:
        nonlocal calls
        calls += 1
        started.set()
        await finish.wait()
        return b"public"

    first = asyncio.create_task(cache.get(("same",), fetch, ttl=10))
    await started.wait()
    second = asyncio.create_task(cache.get(("same",), fetch, ttl=10))
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    finish.set()
    assert await second == b"public"
    assert calls == 1
    assert cache.pending == {}


async def test_failure_is_not_cached_and_next_call_recovers() -> None:
    cache = PublicCache()

    async def failure() -> bytes:
        raise ValueError("upstream failed")

    async def success() -> bytes:
        return b"ok"

    with pytest.raises(ValueError):
        await cache.get(("same",), failure, ttl=10)
    assert cache.entries == {}
    assert cache.pending == {}
    assert await cache.get(("same",), success, ttl=10) == b"ok"


async def test_distinct_fetches_have_a_concurrency_bound() -> None:
    cache = PublicCache()
    started, finish = asyncio.Event(), asyncio.Event()
    active = 0

    async def fetch() -> bytes:
        nonlocal active
        active += 1
        if active == 16:
            started.set()
        await finish.wait()
        return b"ok"

    tasks = [asyncio.create_task(cache.get((str(i),), fetch, ttl=1)) for i in range(16)]
    await started.wait()
    with pytest.raises(CacheBusy):
        await cache.get(("extra",), fetch, ttl=1)
    finish.set()
    await asyncio.gather(*tasks)
    assert not cache.pending
