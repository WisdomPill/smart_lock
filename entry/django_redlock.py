import logging
import threading
import time as mod_time
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

from django.db import IntegrityError
from django.db.transaction import atomic
from redis.exceptions import LockError, LockNotOwnedError

from entry.models import Lock

logger = logging.getLogger(__name__)


class DjangoRedlock:
    """
    Redlock implementation using Django's ORM
    """

    # KEYS[1] - lock name
    # ARGV[1] - token
    # return 1 if the lock was released, otherwise 0
    LUA_RELEASE_SCRIPT = """
        local token = redis.call('get', KEYS[1])
        if not token or token ~= ARGV[1] then
            return 0
        end
        redis.call('del', KEYS[1])
        return 1
    """

    # KEYS[1] - lock name
    # ARGV[1] - token
    # ARGV[2] - additional milliseconds
    # ARGV[3] - "0" if the additional time should be added to the lock's
    #           existing ttl or "1" if the existing ttl should be replaced
    # return 1 if the locks time was extended, otherwise 0
    LUA_EXTEND_SCRIPT = """
        local token = redis.call('get', KEYS[1])
        if not token or token ~= ARGV[1] then
            return 0
        end
        local expiration = redis.call('pttl', KEYS[1])
        if not expiration then
            expiration = 0
        end
        if expiration < 0 then
            return 0
        end

        local newttl = ARGV[2]
        if ARGV[3] == "0" then
            newttl = ARGV[2] + expiration
        end
        redis.call('pexpire', KEYS[1], newttl)
        return 1
    """

    # KEYS[1] - lock name
    # ARGV[1] - token
    # ARGV[2] - milliseconds
    # return 1 if the locks time was reacquired, otherwise 0
    LUA_REACQUIRE_SCRIPT = """
        local token = redis.call('get', KEYS[1])
        if not token or token ~= ARGV[1] then
            return 0
        end
        redis.call('pexpire', KEYS[1], ARGV[2])
        return 1
    """

    def __init__(
        self,
        name,
        timeout=None,
        sleep=0.1,
        blocking=True,
        blocking_timeout=None,
        thread_local=True,
    ):
        """
        Create a new Lock instance named ``name`` using the Redis client
        supplied by ``redis``.

        ``timeout`` indicates a maximum life for the lock in seconds.
        By default, it will remain locked until release() is called.
        ``timeout`` can be specified as a float or integer, both representing
        the number of seconds to wait.

        ``sleep`` indicates the amount of time to sleep in seconds per loop
        iteration when the lock is in blocking mode and another client is
        currently holding the lock.

        ``blocking`` indicates whether calling ``acquire`` should block until
        the lock has been acquired or to fail immediately, causing ``acquire``
        to return False and the lock not being acquired. Defaults to True.
        Note this value can be overridden by passing a ``blocking``
        argument to ``acquire``.

        ``blocking_timeout`` indicates the maximum amount of time in seconds to
        spend trying to acquire the lock. A value of ``None`` indicates
        continue trying forever. ``blocking_timeout`` can be specified as a
        float or integer, both representing the number of seconds to wait.

        ``thread_local`` indicates whether the lock token is placed in
        thread-local storage. By default, the token is placed in thread local
        storage so that a thread only sees its token, not a token set by
        another thread. Consider the following timeline:

            time: 0, thread-1 acquires `my-lock`, with a timeout of 5 seconds.
                     thread-1 sets the token to "abc"
            time: 1, thread-2 blocks trying to acquire `my-lock` using the
                     Lock instance.
            time: 5, thread-1 has not yet completed. redis expires the lock
                     key.
            time: 5, thread-2 acquired `my-lock` now that it's available.
                     thread-2 sets the token to "xyz"
            time: 6, thread-1 finishes its work and calls release(). if the
                     token is *not* stored in thread local storage, then
                     thread-1 would see the token value as "xyz" and would be
                     able to successfully release the thread-2's lock.

        In some use cases it's necessary to disable thread local storage. For
        example, if you have code where one thread acquires a lock and passes
        that lock instance to a worker thread to release later. If thread
        local storage isn't disabled in this case, the worker thread won't see
        the token set by the thread that acquired the lock. Our assumption
        is that these cases aren't common and as such default to using
        thread local storage.
        """
        self.name = name
        self.timeout = timeout
        self.sleep = sleep
        self.blocking = blocking
        self.blocking_timeout = blocking_timeout
        self.thread_local = bool(thread_local)
        self.local = threading.local() if self.thread_local else SimpleNamespace()
        self.local.token = None

    def __enter__(self):
        if self.acquire():
            return self
        raise LockError("Unable to acquire lock within the time specified")

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

    def acquire(self, blocking=None, blocking_timeout=None, token=None):
        """
        Use Django's ORM to hold a shared, distributed lock named ``name``.
        Returns True once the lock is acquired.

        If ``blocking`` is False, always return immediately. If the lock
        was acquired, return True, otherwise return False.

        ``blocking_timeout`` specifies the maximum number of seconds to
        wait trying to acquire the lock.

        ``token`` specifies the token value to be used. If provided, token
        must be a bytes object or a string that can be encoded to a bytes
        object with the default encoding. If a token isn't specified, a UUID
        will be generated.
        """
        sleep = self.sleep
        if token is None:
            token = uuid.uuid4().hex
        if blocking is None:
            blocking = self.blocking
        if blocking_timeout is None:
            blocking_timeout = self.blocking_timeout
        stop_trying_at = None
        if blocking_timeout is not None:
            stop_trying_at = mod_time.monotonic() + blocking_timeout
        while True:
            if self.do_acquire(token):
                self.local.token = token
                return True
            if not blocking:
                return False
            next_try_at = mod_time.monotonic() + sleep
            if stop_trying_at is not None and next_try_at > stop_trying_at:
                return False
            mod_time.sleep(sleep)

    def do_acquire(self, token):
        if self.timeout:
            timeout = self.timeout
        else:
            timeout = None
        if self.create_lock_or_renew_it(token, timeout):
            return True
        return False

    def create_lock_or_renew_it(self, token: str, timeout: int):
        success = False

        try:
            with atomic():
                Lock.objects.select_for_update().create(name=self.name, token=token, timeout=timeout)
                success = True
        except IntegrityError:
            logger.warning("Lock already exists")

            try:
                with atomic():
                    lock = Lock.objects.select_for_update().get(name=self.name)

                    if (
                        lock.timeout is not None
                        and lock.created_at + timedelta(milliseconds=lock.timeout)
                        > datetime.now()
                    ):
                        # lock expired, save it again to update timeout and created_at
                        lock.timeout = timeout
                        lock.save()
                        success = True
                    else:
                        logger.warning("Lock is taken by somebody else")
            except Lock.DoesNotExist:
                logger.warning("Lock got deleted before")

        return success

    def locked(self):
        """
        Returns True if this key is locked by any process, otherwise False.
        """
        return Lock.objects.filter(name=self.name).exists()

    def owned(self):
        """
        Returns True if this key is locked by this lock, otherwise False.
        """
        try:
            lock = Lock.objects.get(name=self.name)

            within_timeout = (
                lock.timeout is not None
                and lock.created_at + timedelta(milliseconds=lock.timeout) > datetime.now()
            )
            no_timeout = lock.timeout is None

            # token is set, lock token is the same as thread local one and (timeout is not set, or we are within timeout)
            return (
                self.local.token is not None
                and lock.token == self.local.token
                and (within_timeout or no_timeout)
            )
        except Lock.DoesNotExist:
            return False

    def release(self):
        "Releases the already acquired lock"
        expected_token = self.local.token
        if expected_token is None:
            raise LockError("Cannot release an unlocked lock")
        self.local.token = None
        self.do_release(expected_token)

    def do_release(self, expected_token: str):
        with atomic():
            try:
                lock = Lock.objects.select_for_update().get(name=self.name)

                if lock.token == expected_token:
                    lock.delete()
                else:
                    raise LockNotOwnedError("Cannot release a lock" " that's no longer owned")
            except Lock.DoesNotExist:
                logger.warning("lock does not exists, it was already released")

    def extend(self, additional_time, replace_ttl=False):
        """
        Adds more time to an already acquired lock.

        ``additional_time`` can be specified as an integer or a float, both
        representing the number of seconds to add.

        ``replace_ttl`` if False (the default), add `additional_time` to
        the lock's existing ttl. If True, replace the lock's ttl with
        `additional_time`.
        """
        if self.local.token is None:
            raise LockError("Cannot extend an unlocked lock")
        if self.timeout is None:
            raise LockError("Cannot extend a lock with no timeout")
        return self.do_extend(additional_time, replace_ttl)

    def do_extend(self, additional_time, replace_ttl):
        additional_time = additional_time

        success = False

        with atomic():
            try:
                lock = Lock.objects.select_for_update().get(name=self.name)

                if lock.token == self.local.token:
                    if replace_ttl:
                        lock.timeout = additional_time
                    else:
                        lock.timeout += additional_time
                    lock.save()

                    success = True
                else:
                    raise LockNotOwnedError("Cannot release a lock that's no longer owned")
            except Lock.DoesNotExist:
                raise LockNotOwnedError("Cannot extend a lock that's no longer owned")

        return success

    def reacquire(self):
        """
        Resets a TTL of an already acquired lock back to a timeout value.
        """
        if self.local.token is None:
            raise LockError("Cannot reacquire an unlocked lock")
        if self.timeout is None:
            raise LockError("Cannot reacquire a lock with no timeout")
        return self.do_reacquire()

    def do_reacquire(self):
        return self.do_extend(self.timeout, replace_ttl=True)
