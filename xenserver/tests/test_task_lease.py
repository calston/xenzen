"""
Tests for task leases.
"""

from datetime import timedelta

from django.contrib.sessions.models import Session
from django.utils import timezone
import pytest

from xenserver.task_lease import _key, acquire, release


def session_object_exists(task, args, **filterkw):
    return Session.objects.filter(
        session_key=_key(task, args), **filterkw).exists()


def session_object_expires_in(task, args, ttl):
    # Allow a couple of seconds either side because of variable test timings.
    now = timezone.now()
    range_start = now + timedelta(seconds=ttl - 2)
    range_end = now + timedelta(seconds=ttl + 2)
    return session_object_exists(
        task, args, expire_date__gt=range_start, expire_date__lt=range_end)


def session_object_expired(task, args):
    return session_object_exists(task, args, expire_date__lt=timezone.now())


def session_object_unexpired(task, args):
    return session_object_exists(task, args, expire_date__gt=timezone.now())


@pytest.mark.django_db
class TestTaskLease(object):
    def test_acquire_new_lease(self, settings):
        """
        We can acquire a new lease for a task.
        """
        settings.XENZEN_TASK_LEASE_SECONDS = 10
        assert not session_object_exists('some_task', 'new_lease_1')
        assert acquire('some_task', 'new_lease_1')
        assert session_object_unexpired('some_task', 'new_lease_1')

    def test_acquire_existing_lease(self, settings):
        """
        We can't acquire an existing lease for a task.
        """
        settings.XENZEN_TASK_LEASE_SECONDS = 10
        assert acquire('some_task', 'existing_lease_1')
        assert session_object_unexpired('some_task', 'existing_lease_1')
        assert not acquire('some_task', 'existing_lease_1')

    def test_acquire_expired_lease(self, settings):
        """
        We can acquire an expired lease for a task.
        """
        settings.XENZEN_TASK_LEASE_SECONDS = -1
        assert acquire('some_task', 'expired_lease_1')
        assert session_object_expired('some_task', 'expired_lease_1')
        settings.XENZEN_TASK_LEASE_SECONDS = 10
        assert acquire('some_task', 'expired_lease_1')
        assert session_object_unexpired('some_task', 'expired_lease_1')

    def test_release_lease(self, settings):
        """
        Releasing a lease deletes it.
        """
        settings.XENZEN_TASK_LEASE_SECONDS = 10
        assert acquire('some_task', 're_lease_1')
        assert session_object_unexpired('some_task', 're_lease_1')
        release('some_task', 're_lease_1')
        assert not session_object_exists('some_task', 're_lease_1')

    def test_release_expired_lease(self, settings):
        """
        Releasing an expired lease deletes it.
        """
        settings.XENZEN_TASK_LEASE_SECONDS = -1
        assert acquire('some_task', 'expired_lease_1')
        assert session_object_expired('some_task', 'expired_lease_1')
        release('some_task', 'expired_lease_1')
        assert not session_object_exists('some_task', 'expired_lease_1')

    def test_release_missing_lease(self, settings):
        """
        Releasing a lease that does not exist does nothing.
        """
        settings.XENZEN_TASK_LEASE_SECONDS = 10
        assert not session_object_exists('some_task', 'missing_lease_1')
        release('some_task', 'missing_lease_1')
        assert not session_object_exists('some_task', 'missing_lease_1')

    def test_acquire_release_acquire(self, settings):
        """
        We can acquire a lease, release it, then acquire it again.
        """
        settings.XENZEN_TASK_LEASE_SECONDS = 10
        assert acquire('some_task', 'lease_1')
        assert session_object_unexpired('some_task', 'lease_1')
        release('some_task', 'lease_1')
        assert not session_object_exists('some_task', 'lease_1')
        assert acquire('some_task', 'lease_1')
        assert session_object_unexpired('some_task', 'lease_1')

    def test_default_ttl(self, settings):
        """
        By default, a new lease has a TTL configured from settings.
        """
        settings.XENZEN_TASK_LEASE_SECONDS = 10
        assert acquire('some_task', 'new_lease_1')
        assert session_object_expires_in('some_task', 'new_lease_1', 10)
        assert not session_object_expires_in('some_task', 'new_lease_1', 0)
        assert not session_object_expires_in('some_task', 'new_lease_1', 20)

    def test_custom_ttl(self, settings):
        """
        A custom TTL can be provided if desired.
        """
        settings.XENZEN_TASK_LEASE_SECONDS = 10
        assert acquire('some_task', 'new_lease_1', 20)
        assert session_object_expires_in('some_task', 'new_lease_1', 20)
        assert not session_object_expires_in('some_task', 'new_lease_1', 10)
        assert not session_object_expires_in('some_task', 'new_lease_1', 30)
