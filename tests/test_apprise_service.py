"""Unit tests for services.notifications.apprise_service."""

from unittest.mock import AsyncMock, patch

import apprise
import pytest

from services.notifications.apprise_service import AppriseService, apprise_enabled


# ------------------------------------------------------------------ #
# Kill-switch                                                          #
# ------------------------------------------------------------------ #
def test_apprise_enabled_default_off(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_APPRISE", raising=False)
    assert apprise_enabled() is False


def test_apprise_enabled_on(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_APPRISE", "on")
    assert apprise_enabled() is True


# ------------------------------------------------------------------ #
# AppriseService                                                       #
# ------------------------------------------------------------------ #
def test_add_channel_success():
    svc = AppriseService()
    with patch.object(svc._apobj, "add", return_value=True) as mock_add:
        result = svc.add_channel("discord://token/123")
    assert result is True
    mock_add.assert_called_once_with("discord://token/123")


def test_add_channel_failure():
    svc = AppriseService()
    with patch.object(svc._apobj, "add", return_value=False):
        result = svc.add_channel("bad://url")
    assert result is False


def test_add_channel_exception():
    svc = AppriseService()
    with patch.object(svc._apobj, "add", side_effect=RuntimeError("boom")):
        result = svc.add_channel("err://url")
    assert result is False


def test_add_channels_multiple():
    svc = AppriseService()
    # All succeed
    with patch.object(svc._apobj, "add", return_value=True):
        count = svc.add_channels(["a://1", "b://2", "c://3"])
    assert count == 3

    # Mixed: one failure
    with patch.object(svc._apobj, "add", side_effect=[True, False, True]):
        count = svc.add_channels(["a://1", "b://2", "c://3"])
    assert count == 2


def test_channel_count():
    svc = AppriseService()
    # len() resolves __len__ on the TYPE, not the instance — patch the class.
    with patch.object(apprise.Apprise, "__len__", return_value=5):
        assert svc.channel_count == 5


@pytest.mark.asyncio
async def test_notify_success():
    svc = AppriseService()
    # Apprise() has __len__ == 0 (falsy) so notify() short-circuits before
    # async_notify — patch __len__ on the class so the guard passes.
    with patch.object(apprise.Apprise, "__len__", return_value=1):
        with patch.object(svc._apobj, "async_notify", new_callable=AsyncMock, return_value=True) as mock_notify:
            result = await svc.notify("Hello", title="Test", tags=["info"])
    assert result is True
    mock_notify.assert_called_once_with(body="Hello", title="Test", tag=["info"])


@pytest.mark.asyncio
async def test_notify_failure():
    svc = AppriseService()
    with patch.object(apprise.Apprise, "__len__", return_value=1):
        with patch.object(svc._apobj, "async_notify", new_callable=AsyncMock, return_value=False):
            result = await svc.notify("fail")
    assert result is False


@pytest.mark.asyncio
async def test_notify_exception():
    svc = AppriseService()
    with patch.object(apprise.Apprise, "__len__", return_value=1):
        with patch.object(svc._apobj, "async_notify", new_callable=AsyncMock, side_effect=RuntimeError("down")):
            result = await svc.notify("boom")
    assert result is False


@pytest.mark.asyncio
async def test_notify_no_channels():
    svc = AppriseService()
    # Empty Apprise object -> len == 0
    with patch.object(apprise.Apprise, "__len__", return_value=0):
        result = await svc.notify("empty")
    assert result is False


def test_reset():
    svc = AppriseService()
    with patch.object(svc._apobj, "add", return_value=True):
        svc.add_channel("test://1")
    svc.reset()
    assert svc.channel_count == 0
