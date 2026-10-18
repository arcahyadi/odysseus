"""M3.5 (safe slice) — drop the redundant ChannelType.EMAIL/WEBHOOK arms.

Cartography verdict: the EMAIL/WEBHOOK enum members duplicate mature native
subsystems (email pollers + webhook_manager) and have zero code callers — no
adapter is ever registered for them, so gateway.send() never delivered via
them. These tests pin that only the two real in-process channels remain and
that the send route degrades gracefully on an unknown channel string.
"""

import asyncio

from src.channel_gateway import ChannelType


def run(coro):
    return asyncio.run(coro)


def test_channel_type_has_only_discord_and_telegram():
    assert {c.name for c in ChannelType} == {"DISCORD", "TELEGRAM"}


def test_email_and_webhook_arms_are_gone():
    assert not hasattr(ChannelType, "EMAIL")
    assert not hasattr(ChannelType, "WEBHOOK")


def test_real_channels_still_construct_from_value():
    assert ChannelType("discord") is ChannelType.DISCORD
    assert ChannelType("telegram") is ChannelType.TELEGRAM


def test_removed_channel_string_no_longer_constructs():
    for dead in ("email", "webhook"):
        try:
            ChannelType(dead)
            assert False, f"{dead} should no longer be a ChannelType"
        except ValueError:
            pass


def test_send_route_degrades_gracefully_on_unknown_channel():
    import routes.channel_routes as cr

    req = cr.SendMessageRequest(channel="email", recipient_id="x", content="hi")
    out = run(cr.send_message(req))
    assert out["ok"] is False
    assert "error" in out
