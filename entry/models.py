from datetime import datetime

from django.db import models


class Lock(models.Model):
    name = models.CharField(max_length=32, primary_key=True)
    token = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now=True)
    timeout = models.FloatField(null=True)

    @property
    def elapsed(self) -> float:
        return (datetime.now() - self.created_at).total_seconds()

    def _ttl(self, elapsed: int) -> int:
        if self.timeout is None:
            time_to_live = -1
        else:
            time_to_live = self.timeout - elapsed

        return time_to_live

    @property
    def ttl(self) -> int:
        time_to_live = self.pttl

        if time_to_live == -1:
            return time_to_live
        else:
            return int(time_to_live / 1000)

    @property
    def pttl(self) -> int:
        elapsed = int(self.elapsed * 1000)

        if self.timeout is None:
            time_to_live = -1
        else:
            time_to_live = int(self.timeout * 1000) - elapsed

        return time_to_live


class Entry(models.Model):
    key = models.CharField(primary_key=True, max_length=32)
    value = models.IntegerField(default=1)
