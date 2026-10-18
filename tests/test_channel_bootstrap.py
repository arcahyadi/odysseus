"""M3.5 — wake the dormant Discord/Telegram channel adapters.

These tests pin the gated in-process wake-up wiring:

- default-OFF kill-switches ODYSSEUS_INPROCESS_DISCORD / ODYSSEUS_INPROCESS_TELEGRAM
  (mirroring src/orchestrator/phase_tracker.tracker_enabled());
- inbound channel messages -> event_bus.fire_event(...);
- outbound OutboundMessage -> native gateway delivery;
- everything best-effort (never raises into the app).

No real Discord/Telegram connection is ever opened: adapters/gateway are fakes.
"""

import asyncio

import pytest

import src.channel_bootstrap as cb
from src.channel_gateway import (
    ChannelGateway,
    ChannelType,
    InboundMessage,
    OutboundMessage,
)


# --------------------------------------------------------------------------- #
# Fakes                                                                        #
# --------------------------------------------------------------------------- #
class FakeAdapter:
    """A ChannelAdapter stand-in that never touches the network."""

    def __init__(self, channel: ChannelType):
        self._channel = channel
        self.started = False
        self.sent: list[OutboundMessage] = []

    @property
    def channel_type(self) -> ChannelType:
        return self._channel

    async def send(self, message: OutboundMessage) -> bool:
        self.sent.append(message)
        return True

    async def start_listening(self, on_message):
        self.started = True


def _clear_gates(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_INPROCESS_DISCORD", raising=False)
    monkeypatch.delenv("ODYSSEUS_INPROCESS_TELEGRAM", raising=False)


# --------------------------------------------------------------------------- #
# Kill-switches: default OFF, mirroring tracker_enabled()                      #
# --------------------------------------------------------------------------- #
def test_discord_gate_default_off(monkeypatch):
    _clear_gates(monkeypatch)
    assert cb.discord_inprocess_enabled() is False


def test_telegram_gate_default_off(monkeypatch):
    _clear_gates(monkeypatch)
    assert cb.telegram_inprocess_enabled() is False


@pytest.mark.parametrize("val", ["on", "1", "true", "yes", "ON", "True"])
def test_discord_gate_truthy_values(monkeypatch, val):
    monkeypatch.setenv("ODYSSEUS_INPROCESS_DISCORD", val)
    assert cb.discord_inprocess_enabled() is True


@pytest.mark.parametrize("val", ["off", "0", "false", "no", ""])
def test_telegram_gate_falsy_values(monkeypatch, val):
    monkeypatch.setenv("ODYSSEUS_INPROCESS_TELEGRAM", val)
    assert cb.telegram_inprocess_enabled() is False


# --------------------------------------------------------------------------- #
# bootstrap_channels: default OFF -> no adapters started at all                #
# --------------------------------------------------------------------------- #
def test_bootstrap_noop_when_both_gates_off(monkeypatch):
    _clear_gates(monkeypatch)
    gw = ChannelGateway()

    made = []

    def _factory(channel):
        a = FakeAdapter(channel)
        made.append(a)
        return a

    started = asyncio.run(cb.bootstrap_channels(gateway=gw, adapter_factory=_factory))

    assert started == []
    assert made == []
    assert gw._adapters == {}
    assert gw._inbound_handler is None


# --------------------------------------------------------------------------- #
# bootstrap_channels: gate ON -> register + set_inbound_handler + start_all    #
# --------------------------------------------------------------------------- #
def test_bootstrap_starts_discord_when_gated_on(monkeypatch):
    _clear_gates(monkeypatch)
    monkeypatch.setenv("ODYSSEUS_INPROCESS_DISCORD", "on")
    gw = ChannelGateway()

    made = {}

    def _factory(channel):
        a = FakeAdapter(channel)
        made[channel] = a
        return a

    started = asyncio.run(cb.bootstrap_channels(gateway=gw, adapter_factory=_factory))

    assert ChannelType.DISCORD in gw._adapters
    assert ChannelType.TELEGRAM not in gw._adapters
    assert gw._inbound_handler is not None
    assert made[ChannelType.DISCORD].started is True
    assert ChannelType.DISCORD in started


def test_bootstrap_starts_both_when_both_gated_on(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_INPROCESS_DISCORD", "1")
    monkeypatch.setenv("ODYSSEUS_INPROCESS_TELEGRAM", "1")
    gw = ChannelGateway()

    def _factory(channel):
        return FakeAdapter(channel)

    started = asyncio.run(cb.bootstrap_channels(gateway=gw, adapter_factory=_factory))

    assert set(started) == {ChannelType.DISCORD, ChannelType.TELEGRAM}
    assert set(gw._adapters) == {ChannelType.DISCORD, ChannelType.TELEGRAM}


# --------------------------------------------------------------------------- #
# inbound -> event_bus.fire_event(...)                                         #
# --------------------------------------------------------------------------- #
def test_inbound_handler_fires_event(monkeypatch):
    fired = []
    handler = cb.make_inbound_handler(fire_event=lambda name, owner=None: fired.append((name, owner)))

    inbound = InboundMessage(
        channel=ChannelType.DISCORD,
        sender_id="42",
        sender_name="alice",
        content="hello",
        raw={},
    )
    asyncio.run(handler(inbound))

    assert len(fired) == 1
    name, owner = fired[0]
    assert "discord" in name.lower()


def test_inbound_handler_best_effort_swallows_errors(monkeypatch):
    def _boom(name, owner=None):
        raise RuntimeError("bus down")

    handler = cb.make_inbound_handler(fire_event=_boom)
    inbound = InboundMessage(
        channel=ChannelType.TELEGRAM,
        sender_id="1",
        sender_name="bob",
        content="hi",
        raw={},
    )
    # Must not raise.
    asyncio.run(handler(inbound))


# --------------------------------------------------------------------------- #
# outbound -> native gateway delivery                                         #
# --------------------------------------------------------------------------- #
def test_outbound_delivers_via_gateway(monkeypatch):
    gw = ChannelGateway()
    adapter = FakeAdapter(ChannelType.DISCORD)
    gw.register_adapter(adapter)

    msg = OutboundMessage(channel=ChannelType.DISCORD, recipient_id="123", content="pong")
    ok = asyncio.run(cb.deliver_outbound(msg, gateway=gw))

    assert ok is True
    assert adapter.sent == [msg]


def test_outbound_best_effort_when_no_adapter(monkeypatch):
    gw = ChannelGateway()  # nothing registered
    msg = OutboundMessage(channel=ChannelType.TELEGRAM, recipient_id="1", content="x")
    # No adapter -> False, but never raises.
    ok = asyncio.run(cb.deliver_outbound(msg, gateway=gw))
    assert ok is False


# --------------------------------------------------------------------------- #
# Agent-reply round-trip: gated ODYSSEUS_CHANNEL_AGENT_REPLY (default OFF)     #
# --------------------------------------------------------------------------- #
def _inbound(reply_sink=None):
    async def _reply(text):
        if reply_sink is not None:
            reply_sink.append(text)

    return InboundMessage(
        channel=ChannelType.DISCORD,
        sender_id="42",
        sender_name="alice",
        content="what's the weather?",
        raw={},
        reply_fn=_reply if reply_sink is not None else None,
    )


def test_agent_reply_gate_default_off(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_CHANNEL_AGENT_REPLY", raising=False)
    assert cb.channel_agent_reply_enabled() is False


def test_inbound_gate_off_does_not_run_agent(monkeypatch):
    monkeypatch.delenv("ODYSSEUS_CHANNEL_AGENT_REPLY", raising=False)
    fired, replies = [], []
    called = {"agent": False}

    async def _agent(messages, owner=None):
        called["agent"] = True
        return "should not be called"

    handler = cb.make_inbound_handler(
        fire_event=lambda name, owner=None: fired.append(name),
        agent_call=_agent,
    )
    asyncio.run(handler(_inbound(reply_sink=replies)))

    assert called["agent"] is False
    assert replies == []
    assert len(fired) == 1  # event still fires (observability preserved)


def test_inbound_gate_on_runs_agent_and_replies(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_CHANNEL_AGENT_REPLY", "on")
    fired, replies = [], []

    async def _agent(messages, owner=None):
        # native one-shot contract: system + user message, returns text
        assert messages[-1]["content"] == "what's the weather?"
        return "It's sunny."

    handler = cb.make_inbound_handler(
        fire_event=lambda name, owner=None: fired.append(name),
        agent_call=_agent,
    )
    asyncio.run(handler(_inbound(reply_sink=replies)))

    assert replies == ["It's sunny."]
    assert len(fired) == 1  # event fires regardless


def test_agent_reply_falls_back_to_gateway_when_no_reply_fn(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_CHANNEL_AGENT_REPLY", "on")
    gw = ChannelGateway()
    adapter = FakeAdapter(ChannelType.DISCORD)
    gw.register_adapter(adapter)

    async def _agent(messages, owner=None):
        return "pong"

    msg = _inbound(reply_sink=None)  # no reply_fn
    asyncio.run(cb.run_agent_reply(msg, agent_call=_agent, gateway=gw))

    assert len(adapter.sent) == 1
    assert adapter.sent[0].content == "pong"
    assert adapter.sent[0].recipient_id == "42"


def test_agent_reply_best_effort_when_agent_raises(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_CHANNEL_AGENT_REPLY", "on")
    replies = []

    async def _boom(messages, owner=None):
        raise RuntimeError("llm down")

    msg = _inbound(reply_sink=replies)
    # Must not raise, must not reply.
    out = asyncio.run(cb.run_agent_reply(msg, agent_call=_boom))
    assert out is None
    assert replies == []


def test_agent_reply_skips_empty_content(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_CHANNEL_AGENT_REPLY", "on")
    replies = []
    called = {"agent": False}

    async def _agent(messages, owner=None):
        called["agent"] = True
        return "x"

    msg = InboundMessage(
        channel=ChannelType.DISCORD,
        sender_id="1",
        sender_name="a",
        content="   ",
        raw={},
        reply_fn=lambda text: replies.append(text),
    )
    out = asyncio.run(cb.run_agent_reply(msg, agent_call=_agent))
    assert out is None
    assert called["agent"] is False
    assert replies == []
