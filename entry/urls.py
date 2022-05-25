from django.urls import path

from entry.views import (
    DjangoEntryDjangoLockView,
    DjangoEntryRedisLockView,
    RedisEntryDjangoLockView,
    RedisEntryRedisLockView,
)

app_name = "entry"

urlpatterns = [
    # django model, django redlock
    path("django/django/lock/<str:key>/", DjangoEntryDjangoLockView.as_view()),
    # django model, django redlock
    path("django/redis/lock/<str:key>/", DjangoEntryRedisLockView.as_view()),
    # redis model, django redlock
    path("redis/django/lock/<str:key>/", RedisEntryDjangoLockView.as_view()),
    # redis model, redis redlock
    path("redis/redis/lock/<str:key>/", RedisEntryRedisLockView.as_view()),
]
