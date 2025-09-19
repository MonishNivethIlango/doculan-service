import inspect
import time
import uuid
from functools import wraps
from fastapi import HTTPException


class RedisDistributedLock:
    def __init__(self, redis_client, key: str, ttl: int = 15):
        self.redis_client = redis_client
        self.key = f"lock:{key}"
        self.ttl = ttl
        self.lock_token = str(uuid.uuid4())

    def acquire(self, retry_interval: float = 0.5, max_retries: int = 20):
        for _ in range(max_retries):
            if self.redis_client.set(self.key, self.lock_token, nx=True, ex=self.ttl):
                return True
            time.sleep(retry_interval)
        raise HTTPException(status_code=409, detail=f"Could not acquire lock for key: {self.key}")

    def release(self):
        # Safe release via Lua script
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        self.redis_client.eval(lua_script, 1, self.key, self.lock_token)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def with_redis_lock(redis_client, lock_key_template: str, ttl: int = 15):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            lock_key = resolve_lock_key(func, args, kwargs, lock_key_template)
            with RedisDistributedLock(redis_client, lock_key, ttl):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            lock_key = resolve_lock_key(func, args, kwargs, lock_key_template)
            with RedisDistributedLock(redis_client, lock_key, ttl):
                return func(*args, **kwargs)

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def resolve_lock_key(func, args, kwargs, template: str) -> str:
    """Resolve formatted lock key from function arguments."""
    sig = inspect.signature(func)
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()

    format_kwargs = {}
    for name, val in bound.arguments.items():
        if hasattr(val, '__dict__'):
            format_kwargs.update(val.__dict__)
        else:
            format_kwargs[name] = val

    try:
        return template.format(**format_kwargs)
    except KeyError as e:
        raise HTTPException(status_code=500, detail=f"Missing key for lock key template: {e}")
