"""channel_bootstrap.py — wake the dormant Discord/Telegram adapters (M3.5).

The Discord/Telegram adapters (src/adapters/*) and the ChannelGateway
(src/channel_gateway.py) already exist but have zero in-process callers, so the
gateway never runs live. This module is the single, kill-switched wake-up point
that `_startup_event` calls:

    - inbound  : adapter -> gateway inbound handler -> event_bus.fire_event(...)
    - outbound : OutboundMessage -> gateway.send(...) (native delivery)

SAFETY: each channel is OFF by default behind its own kill-switch
(ODYSSEUS_INPROCESS_DISCORD / ODYSSEUS_INPROCESS_TELEGRAM), mirroring
src/orchestrator/phase_tracker.tracker_enabled(). With both OFF (the default),
bootstrap_channels() registers nothing and starts nothing, so startup behaviour
is byte-identical to today. Everything here is best-effort: a broken adapter,
bus, or bot can never crash the app.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from src.channel_gateway import (
    ChannelGateway,
    ChannelType,
    InboundMessage,
    OutboundMessage,
    get_gateway,
)

logger = logging.getLogger(__name__)

_TRUTHY = {"on", "1", "true", "yes"}


def _gate(env_name: str) -> bool:
    """OFF unless ``env_name`` is set to a truthy value (mirror tracker_enabled)."""
    val = os.getenv(env_name, "off").strip().lower()
    return val in _TRUTHY


def discord_inprocess_enabled() -> bool:
    """OFF unless ODYSSEUS_INPROCESS_DISCORD is truthy."""
    return _gate("ODYSSEUS_INPROCESS_DISCORD")


def telegram_inprocess_enabled() -> bool:
    """OFF unless ODYSSEUS_INPROCESS_TELEGRAM is truthy."""
    return _gate("ODYSSEUS_INPROCESS_TELEGRAM")


def channel_agent_reply_enabled() -> bool:
    """OFF unless ODYSSEUS_CHANNEL_AGENT_REPLY is truthy.

    Gates the inbound -> agent -> reply round-trip. With this OFF (the default),
    inbound handling is byte-identical to before: fire the trigger event only.
    """
    return _gate("ODYSSEUS_CHANNEL_AGENT_REPLY")


_CHANNEL_SYSTEM_PROMPT = (
    "You are Odysseus replying to a message received on an external chat channel "
    "(Discord/Telegram). Answer the user's message directly and concisely."
)


async def run_agent_reply(
    message: InboundMessage,
    agent_call: Callable | None = None,
    gateway: ChannelGateway | None = None,
) -> str | None:
    """Run the native one-shot agent on ``message.content`` and reply to origin.

    The agent call routes through ``task_endpoint.task_llm_call_async``, the shared
    background-task LLM candidate chain, which resolves endpoint/model/fallback from
    the native ModelEndpoint config — no bespoke provider selection lives here. The
    reply is delivered via the message's own ``reply_fn`` (the adapter's native
    direct-reply callback), falling back to native gateway delivery when absent.

    Stateless one-shot (owner=None, no session). Best-effort: returns the reply
    text on success, or None on empty input or any failure — never raises.
    """
    text = (message.content or "").strip()
    if not text:
        return None

    if agent_call is None:
        from src.task_endpoint import task_llm_call_async

        agent_call = task_llm_call_async

    try:
        messages = [
            {"role": "system", "content": _CHANNEL_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]
        reply = await agent_call(messages, owner=None)
        reply = (reply or "").strip()
    except Exception:
        logger.exception("Channel agent reply generation failed (best-effort)")
        return None

    if not reply:
        return None

    # Prefer the adapter's own direct-reply callback (keeps native thread/context).
    if message.reply_fn is not None:
        try:
            await message.reply_fn(reply)
            return reply
        except Exception:
            logger.exception("Channel direct reply failed; trying gateway (best-effort)")

    # Fallback: native gateway delivery back to the sender.
    try:
        await deliver_outbound(
            OutboundMessage(
                channel=message.channel,
                recipient_id=message.sender_id,
                content=reply,
            ),
            gateway=gateway,
        )
    except Exception:
        logger.exception("Channel gateway reply fallback failed (best-effort)")
    return reply


def make_inbound_handler(
    fire_event: Callable | None = None,
    agent_call: Callable | None = None,
    gateway: ChannelGateway | None = None,
) -> Callable:
    """Build the inbound handler: channel message -> event_bus.fire_event(...).

    The event name is ``channel_message_<channel>`` (e.g. channel_message_discord),
    which event-triggered scheduled tasks can subscribe to. When
    ``channel_agent_reply_enabled()`` is ON, the handler additionally runs the
    native one-shot agent on the message and replies to the sender (see
    ``run_agent_reply``); with it OFF (the default), only the event fires — byte
    -identical to before. Best-effort: any error (bus down, bad payload) is
    swallowed so an inbound message never crashes the adapter's listen loop.
    """
    if fire_event is None:
        from src.event_bus import fire_event as _fire_event

        fire_event = _fire_event

    async def _handler(message: InboundMessage) -> None:
        try:
            event_name = f"channel_message_{message.channel.value}"
            fire_event(event_name, None)
        except Exception:
            logger.exception("Inbound channel message handling failed (best-effort)")

        if channel_agent_reply_enabled():
            await run_agent_reply(message, agent_call=agent_call, gateway=gateway)

    return _handler


async def deliver_outbound(message: OutboundMessage, gateway: ChannelGateway | None = None) -> bool:
    """Deliver an OutboundMessage via native gateway delivery. Best-effort.

    Routes through ChannelGateway.send(), which dispatches to the registered
    adapter for the message's channel. Returns False (never raises) on any error
    or when no adapter is registered.
    """
    gw = gateway or get_gateway()
    try:
        return await gw.send(message)
    except Exception:
        logger.exception("Outbound channel delivery failed (best-effort)")
        return False


def _default_adapter_factory(channel: ChannelType):
    """Build the real adapter for ``channel`` from environment configuration.

    Kept separate so tests can inject a fake factory and never import discord.py
    / python-telegram-bot or open a real connection.
    """
    if channel is ChannelType.DISCORD:
        from src.adapters.discord_adapter import DiscordAdapter

        chan_id = os.getenv("DISCORD_DEFAULT_CHANNEL_ID")
        return DiscordAdapter(
            bot_token=os.getenv("DISCORD_BOT_TOKEN"),
            default_channel_id=int(chan_id) if chan_id else None,
        )
    if channel is ChannelType.TELEGRAM:
        from src.adapters.telegram_adapter import TelegramAdapter

        chat_id = os.getenv("TELEGRAM_DEFAULT_CHAT_ID")
        return TelegramAdapter(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            default_chat_id=int(chat_id) if chat_id else None,
        )
    raise ValueError(f"No adapter factory for channel {channel!r}")


async def bootstrap_channels(
    gateway: ChannelGateway | None = None,
    adapter_factory: Callable[[ChannelType], object] | None = None,
    fire_event: Callable | None = None,
) -> list[ChannelType]:
    """Wake the gated in-process channel adapters. Returns the list started.

    For each channel whose kill-switch is ON: build its adapter, register it on
    the gateway, wire the inbound handler, then start_all() so it begins
    listening. With every gate OFF (the default) this registers nothing, starts
    nothing, and returns []. Fully best-effort — never raises into startup.
    """
    gw = gateway or get_gateway()
    factory = adapter_factory or _default_adapter_factory

    wanted: list[ChannelType] = []
    if discord_inprocess_enabled():
        wanted.append(ChannelType.DISCORD)
    if telegram_inprocess_enabled():
        wanted.append(ChannelType.TELEGRAM)

    if not wanted:
        return []

    started: list[ChannelType] = []
    for channel in wanted:
        try:
            adapter = factory(channel)
            gw.register_adapter(adapter)
            started.append(channel)
        except Exception:
            logger.exception("Failed to register %s adapter (best-effort)", channel)

    if not started:
        return []

    try:
        gw.set_inbound_handler(make_inbound_handler(fire_event=fire_event, gateway=gw))
        await gw.start_all()
    except Exception:
        logger.exception("Failed to start channel adapters (best-effort)")

    logger.info(
        "In-process channel adapters started: %s",
        ", ".join(c.value for c in started),
    )
    return started
