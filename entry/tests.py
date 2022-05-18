import time

import pytest
from redis.exceptions import LockError, LockNotOwnedError

from entry.django_redlock import DjangoRedlock
from entry.models import Lock


@pytest.mark.django_db
class TestLock:
    def get_lock(self, *args, **kwargs):
        return DjangoRedlock(*args, **kwargs)

    def test_lock(self):
        lock = self.get_lock("foo")
        assert lock.acquire(blocking=False)

        db_lock = Lock.objects.get(name="foo")

        assert db_lock.token == lock.local.token
        assert db_lock.ttl == -1
        lock.release()

        with pytest.raises(Lock.DoesNotExist):
            Lock.objects.get(name="foo")

    def test_lock_token(self):
        lock = self.get_lock("foo")
        self._test_lock_token(lock)

    def test_lock_token_thread_local_false(self):
        lock = self.get_lock("foo", thread_local=False)
        self._test_lock_token(lock)

    def _test_lock_token(self, lock: DjangoRedlock):
        assert lock.acquire(blocking=False, token="test")

        db_lock = Lock.objects.get(name="foo")

        assert db_lock.token == lock.local.token
        assert db_lock.ttl == -1
        lock.release()

        with pytest.raises(Lock.DoesNotExist):
            Lock.objects.get(name="foo")

        assert lock.local.token is None

    def test_locked(self):
        lock = self.get_lock("foo")
        assert lock.locked() is False
        lock.acquire(blocking=False)
        assert lock.locked() is True
        lock.release()
        assert lock.locked() is False

    def test_owned(self):
        lock = self.get_lock("foo")
        assert lock.owned() is False
        lock.acquire(blocking=False)
        assert lock.owned() is True
        lock.release()
        assert lock.owned() is False

        lock2 = self.get_lock("foo")
        assert lock.owned() is False
        assert lock2.owned() is False
        lock2.acquire(blocking=False)
        assert lock.owned() is False
        assert lock2.owned() is True
        lock2.release()
        assert lock.owned() is False
        assert lock2.owned() is False

    def test_competing_locks(self):
        lock1 = self.get_lock("foo")
        lock2 = self.get_lock("foo")
        assert lock1.acquire(blocking=False)
        assert not lock2.acquire(blocking=False)
        lock1.release()
        assert lock2.acquire(blocking=False)
        assert not lock1.acquire(blocking=False)
        lock2.release()

    def test_timeout(self):
        lock = self.get_lock("foo", timeout=10)
        assert lock.acquire(blocking=False)

        db_lock = Lock.objects.get(name="foo")
        assert 8 < db_lock.ttl <= 10
        lock.release()

    def test_float_timeout(self):
        lock = self.get_lock("foo", timeout=9.5)
        assert lock.acquire(blocking=False)
        db_lock = Lock.objects.get(name="foo")
        assert 8 < db_lock.pttl <= 9500
        lock.release()

    def test_blocking_timeout(self):
        lock1 = self.get_lock("foo")
        assert lock1.acquire(blocking=False)
        bt = 0.4
        sleep = 0.1
        lock2 = self.get_lock("foo", sleep=sleep, blocking_timeout=bt)
        start = time.monotonic()
        assert not lock2.acquire()
        # The elapsed duration should be less than the total blocking_timeout
        assert bt > (time.monotonic() - start) > bt - sleep
        lock1.release()

    def test_context_manager(self):
        # blocking_timeout prevents a deadlock if the lock can't be acquired
        # for some reason
        with self.get_lock("foo", blocking_timeout=0.2) as lock:
            db_lock = Lock.objects.get(name="foo")

            assert db_lock.token == lock.local.token

        with pytest.raises(Lock.DoesNotExist):
            Lock.objects.get(name="foo")

    def test_context_manager_raises_when_locked_not_acquired(self):
        Lock.objects.create(name="foo", token="bar")
        with pytest.raises(LockError):
            with self.get_lock("foo", blocking_timeout=0.1):
                pass

    def test_high_sleep_small_blocking_timeout(self):
        lock1 = self.get_lock("foo")
        assert lock1.acquire(blocking=False)
        sleep = 60
        bt = 1
        lock2 = self.get_lock("foo", sleep=sleep, blocking_timeout=bt)
        start = time.monotonic()
        assert not lock2.acquire()
        # the elapsed timed is less than the blocking_timeout as the lock is
        # unattainable given the sleep/blocking_timeout configuration
        assert bt > (time.monotonic() - start)
        lock1.release()

    def test_releasing_unlocked_lock_raises_error(self):
        lock = self.get_lock("foo")
        with pytest.raises(LockError):
            lock.release()

    def test_releasing_lock_no_longer_owned_raises_error(self):
        lock = self.get_lock("foo")
        lock.acquire(blocking=False)
        # manually change the token
        db_lock = Lock.objects.get(name="foo")
        db_lock.token = "a"
        db_lock.save()

        with pytest.raises(LockNotOwnedError):
            lock.release()
        # even though we errored, the token is still cleared
        assert lock.local.token is None

    def test_extend_lock(self):
        lock = self.get_lock("foo", timeout=10)
        assert lock.acquire(blocking=False)

        db_lock = Lock.objects.get(name="foo")
        assert 8000 < db_lock.pttl <= 10000
        assert lock.extend(10)
        db_lock.refresh_from_db()
        assert 16000 < db_lock.pttl <= 20000
        lock.release()

    def test_extend_lock_replace_ttl(self):
        lock = self.get_lock("foo", timeout=10)
        assert lock.acquire(blocking=False)

        db_lock = Lock.objects.get(name="foo")
        assert 8000 < db_lock.pttl <= 10000
        assert lock.extend(10, replace_ttl=True)
        db_lock.refresh_from_db()
        assert 8000 < db_lock.pttl <= 10000
        lock.release()

    def test_extend_lock_float(self):
        lock = self.get_lock("foo", timeout=10.0)
        assert lock.acquire(blocking=False)

        db_lock = Lock.objects.get(name="foo")
        assert 8000 < db_lock.pttl <= 10000
        assert lock.extend(10.0)
        db_lock.refresh_from_db()
        assert 16000 < db_lock.pttl <= 20000
        lock.release()

    def test_extending_unlocked_lock_raises_error(self):
        lock = self.get_lock("foo", timeout=10)
        with pytest.raises(LockError):
            lock.extend(10)

    def test_extending_lock_with_no_timeout_raises_error(self):
        lock = self.get_lock("foo")
        assert lock.acquire(blocking=False)
        with pytest.raises(LockError):
            lock.extend(10)
        lock.release()

    def test_extending_lock_no_longer_owned_raises_error(self):
        lock = self.get_lock("foo", timeout=10)
        assert lock.acquire(blocking=False)

        db_lock = Lock.objects.get(name="foo")
        db_lock.token = "a"
        db_lock.save()

        with pytest.raises(LockNotOwnedError):
            lock.extend(10)

    def test_reacquire_lock(self):
        lock = self.get_lock("foo", timeout=10)
        assert lock.acquire(blocking=False)

        db_lock = Lock.objects.get(name="foo")
        db_lock.timeout = 5
        db_lock.save()

        assert db_lock.pttl <= 5000
        assert lock.reacquire()

        db_lock.refresh_from_db()
        assert 8000 < db_lock.pttl <= 10000
        lock.release()

    def test_reacquiring_unlocked_lock_raises_error(self):
        lock = self.get_lock("foo", timeout=10)
        with pytest.raises(LockError):
            lock.reacquire()

    def test_reacquiring_lock_with_no_timeout_raises_error(self):
        lock = self.get_lock("foo")
        assert lock.acquire(blocking=False)
        with pytest.raises(LockError):
            lock.reacquire()
        lock.release()

    def test_reacquiring_lock_no_longer_owned_raises_error(self):
        lock = self.get_lock("foo", timeout=10)
        assert lock.acquire(blocking=False)

        db_lock = Lock.objects.get(name="foo")
        db_lock.token = "a"
        db_lock.save()

        with pytest.raises(LockNotOwnedError):
            lock.reacquire()
