"""Tests for AppriseService and kill-switch integration.

Pins:
- ODYSSEUS_APPRISE defaults to OFF (backward-compatible).
- AppriseService.notify() returns True on success, False on failure.
- ChannelGateway delegates to Apprise when kill-switch ON.
- ChannelGateway falls back to legacy adapters when kill-switch OFF.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.channel_gateway import (
    ChannelGateway,
    ChannelType,
    OutboundMessage,
    _apprise_kill_switch,
)


# ------------------------------------------------------------------ #
# Kill-switch                                                          #
# ------------------------------------------------------------------ #
def test_apprise_kill_switch_default_off(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_APPRISE", raising=False)
    assert _apprise_kill_switch() is False


@pytest.mark.parametrize("val", ["on", "1", "true", "yes", "ON", "True"])
def test_apprise_kill_switch_truthy(monkeypatch, val):
    monkeypatch.setenv("ODYSSEUS_APPRISE", val)
    assert _apprise_kill_switch() is True


@pytest.mark.parametrize("val", ["off", "0", "false", "no", ""])
def test_apprise_kill_switch_falsy(monkeypatch, val):
    monkeypatch.setenv("ODYSSEUS_APPRISE", val)
    assert _apprise_kill_switch() is False


# ------------------------------------------------------------------ #
# ChannelGateway.send() routing                                        #
# ------------------------------------------------------------------ #
class FakeAdapter:
    def __init__(self, channel: ChannelType):
        self._channel = channel
        self.sent = []

    @property
    def channel_type(self):
        return self._channel

    async def send(self, message):
        self.sent.append(message)
        return True

    async def start_listening(self, on_message):
        pass


def test_send_uses_legacy_adapter_when_apprise_off(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_APPRISE", raising=False)
    gw = ChannelGateway()
    adapter = FakeAdapter(ChannelType.DISCORD)
    gw.register_adapter(adapter)

    msg = OutboundMessage(channel=ChannelType.DISCORD, recipient_id="1", content="hi")
    ok = asyncio.run(gw.send(msg))
    assert ok is True
    assert adapter.sent == [msg]


def test_send_routes_through_apprise_when_killswitch_on(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_APPRISE", "on")
    gw = ChannelGateway()

    mock_svc = MagicMock()
    mock_svc.notify = AsyncMock(return_value=True)

    with patch("src.channel_gateway._get_apprise_service", return_value=mock_svc):
        msg = OutboundMessage(channel=ChannelType.DISCORD, recipient_id="42", content="hello")
        ok = asyncio.run(gw.send(msg))

    assert ok is True
    mock_svc.notify.assert_called_once_with(
        "hello",
        title="discord:42",
        tags=["discord"],
    )


def test_send_apprise_fallback_when_service_none(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_APPRISE", "on")
    gw = ChannelGateway()

    with patch("src.channel_gateway._get_apprise_service", return_value=None):
        msg = OutboundMessage(channel=ChannelType.TELEGRAM, recipient_id="1", content="x")
        ok = asyncio.run(gw.send(msg))

    assert ok is False


def test_apprise_enabled_property(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_APPRISE", raising=False)
    gw = ChannelGateway()
    assert gw.apprise_enabled is False

    monkeypatch.setenv("ODYSSEUS_APPRISE", "on")
    gw2 = ChannelGateway()
    assert gw2.apprise_enabled is True
