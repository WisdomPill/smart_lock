from typing import Protocol

from django.core.cache import cache
from redis.exceptions import LockError
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_408_REQUEST_TIMEOUT
from rest_framework.views import APIView

from entry.django_redlock import DjangoRedlock
from entry.models import Entry


class BaseViewProtocol(Protocol):
    @staticmethod
    def get_entry_value(key: str) -> int:
        ...

    @staticmethod
    def increment_entry(key: str) -> int:
        ...


class BaseView(APIView, BaseViewProtocol):
    def get(self, request, *args, **kwargs):
        key = kwargs["key"]

        try:
            value = self.get_entry_value(key)

            status = HTTP_200_OK
            data = {"key": key, "value": value}
        except LockError:
            status = HTTP_408_REQUEST_TIMEOUT
            data = {"detail": "request timeout"}

        return Response(data, status=status)

    def post(self, request, *args, **kwargs) -> Response:
        key = kwargs["key"]

        try:
            value = self.increment_entry(key)

            status = HTTP_200_OK
            data = {"key": key, "value": value}
        except LockError:
            status = HTTP_408_REQUEST_TIMEOUT
            data = {"detail": "request timeout"}

        return Response(data, status=status)


class DjangoEntryDjangoLockView(BaseView):
    @staticmethod
    def get_entry_value(key: str) -> int:
        with DjangoRedlock(key, timeout=1):
            entry, created = Entry.objects.get_or_create(key=key)

        return entry.value

    @staticmethod
    def increment_entry(key: str) -> int:
        with DjangoRedlock(key, timeout=1):
            entry, created = Entry.objects.get_or_create(key=key)
            entry.value += 1
            entry.save(update_fields=["value"])

        return entry.value


class DjangoEntryRedisLockView(BaseView):
    @staticmethod
    def get_entry_value(key: str) -> int:
        with cache.lock(f"lock-{key}", timeout=1):
            entry, created = Entry.objects.get_or_create(key=key)

        return entry.value

    @staticmethod
    def increment_entry(key: str) -> int:
        with cache.lock(f"lock-{key}", timeout=1):
            entry, created = Entry.objects.get_or_create(key=key)
            entry.value += 1
            entry.save(update_fields=["value"])

        return entry.value


class RedisEntryDjangoLockView(BaseView):
    @staticmethod
    def get_entry_value(key: str) -> int:
        with DjangoRedlock(key, timeout=1):
            value = cache.get(key)

        return value

    @staticmethod
    def increment_entry(key: str) -> int:
        with DjangoRedlock(key, timeout=1):
            value = cache.incr(key, ignore_key_check=True)

        return value


class RedisEntryRedisLockView(BaseView):
    @staticmethod
    def get_entry_value(key: str) -> int:
        with cache.lock(f"lock-{key}", timeout=1):
            value = cache.get(key)

        return value

    @staticmethod
    def increment_entry(key: str) -> int:
        with cache.lock(f"lock-{key}", timeout=1):
            value = cache.incr(key, ignore_key_check=True)

        return value
