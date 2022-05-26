import pytest
from django_redis import get_redis_connection


@pytest.fixture(autouse=True)
def flush_cache():
    get_redis_connection("default").flushall()
