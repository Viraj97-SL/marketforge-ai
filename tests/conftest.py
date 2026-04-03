"""
Shared pytest configuration.

Forces Redis to an unreachable port so every test module uses SQLite for
deduplication and caching instead of a shared Redis instance that would leak
state between test functions.
"""
import os

# Override any setdefault that individual test files may have already set.
# Port 19999 is unused by convention — Redis will fail immediately and the
# DedupStore / RedisCache will fall back to their SQLite / in-memory paths.
os.environ["REDIS_URL"] = "redis://127.0.0.1:19999/15"
