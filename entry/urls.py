from django.urls import path

from entry.views import (
    DjangoEntryDjangoLockView,
    DjangoEntryRedisLockView,
    RedisEntryDjangoLockView,
    RedisEntryRedisLockView,
)

app_name = "entry"

urlpatterns = [
    path("django/django/lock/<str:key>/", DjangoEntryDjangoLockView.as_view()),
    path("django/redis/lock/<str:key>/", DjangoEntryRedisLockView.as_view()),
    path("redis/django/lock/<str:key>/", RedisEntryDjangoLockView.as_view()),
    path("redis/redis/lock/<str:key>/", RedisEntryRedisLockView.as_view()),
]
