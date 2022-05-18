from random import choice

from django.utils.lorem_ipsum import COMMON_WORDS
from locust import HttpUser, between, task

TIMEOUT = 2


class BaseUser(HttpUser):
    wait_time = between(1, 2)
    url = ""

    def __init__(self, *args, **kwargs):
        super(BaseUser, self).__init__(*args, **kwargs)

        self.key = choice(COMMON_WORDS)

    @task
    def increment_entry(self):
        self.client.post(
            self.url.format(key=self.key),
            name="increment_entry",
            timeout=TIMEOUT,
        )

    @task(3)
    def get_entry(self):
        self.client.get(
            self.url.format(key=self.key),
            name="get_entry",
            timeout=TIMEOUT,
        )


class DjangoEntryDjangoLockUser(BaseUser):
    url = "/entry/django/django/lock/{key}/"


class DjangoEntryRedisLockUser(BaseUser):
    url = "/entry/django/redis/lock/{key}/"


class RedisEntryDjangoLockUser(BaseUser):
    url = "/entry/redis/django/lock/{key}/"


class RedisEntryRedisLockUser(BaseUser):
    url = "/entry/redis/redis/lock/{key}/"
