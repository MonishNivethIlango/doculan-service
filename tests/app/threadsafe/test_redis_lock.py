import pytest
from unittest.mock import MagicMock, patch
from app.threadsafe.redis_lock import RedisDistributedLock, with_redis_lock

# Test RedisDistributedLock acquire/release
def test_redis_distributed_lock_acquire_release():
    redis_client = MagicMock()
    redis_client.set.return_value = True
    lock = RedisDistributedLock(redis_client, 'testkey', ttl=5)
    with lock:
        redis_client.set.assert_called_with('lock:testkey', lock.lock_token, nx=True, ex=5)
    redis_client.eval.assert_called()

# Test with_redis_lock decorator (sync)
def test_with_redis_lock_decorator_sync():
    redis_client = MagicMock()
    redis_client.set.return_value = True
    redis_client.eval.return_value = 1
    calls = []
    @with_redis_lock(redis_client, lock_key_template='mykey:{x}', ttl=3)
    def myfunc(x):
        calls.append(x)
        return x * 2
    result = myfunc(5)
    assert result == 10
    assert calls == [5]
    redis_client.set.assert_called_with('lock:mykey:5', ANY, nx=True, ex=3)
    redis_client.eval.assert_called()

import asyncio
@pytest.mark.asyncio
async def test_with_redis_lock_decorator_async():
    redis_client = MagicMock()
    redis_client.set.return_value = True
    redis_client.eval.return_value = 1
    calls = []
    @with_redis_lock(redis_client, lock_key_template='mykey:{x}', ttl=3)
    async def myfunc(x):
        calls.append(x)
        return x * 3
    result = await myfunc(7)
    assert result == 21
    assert calls == [7]
    redis_client.set.assert_called_with('lock:mykey:7', ANY, nx=True, ex=3)
    redis_client.eval.assert_called()

from unittest.mock import ANY
