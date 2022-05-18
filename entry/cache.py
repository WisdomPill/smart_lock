from django.core.cache import cache


def increment_entry(key: str) -> None:
    cache.incr(key, ignore_key_check=True)
