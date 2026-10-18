"""AppriseService — unified notification layer via Apprise (BSD, 100+ channels).

Usage::

    from services.notifications.apprise_service import AppriseService

    svc = AppriseService()
    svc.add_channel("discord://token/webhook_id")
    svc.add_channel("ntfy://mytopic")
    await svc.notify("Hello world!")
    await svc.notify("Task done", tags=["success"])

When ``ODYSSEUS_APPRISE`` is OFF (the default), ``ChannelGateway`` keeps using the
legacy individual adapters.  When it is ON, outbound messages are routed through
this service instead.

Best-effort: every public method swallows exceptions and logs, never raising.
"""

from __future__ import annotations

import logging
import os

import apprise

logger = logging.getLogger(__name__)

_TRUTHY = {"on", "1", "true", "yes"}


def apprise_enabled() -> bool:
    """Return True if the ODYSSEUS_APPRISE kill-switch is ON.

    The env var is checked at call-time so the switch can be flipped without a
    restart (consistent with the existing ``_gate`` pattern in
    ``channel_bootstrap``).
    """
    val = os.getenv("ODYSSEUS_APPRISE", "off").strip().lower()
    return val in _TRUTHY


class AppriseService:
    """Thin wrapper around ``apprise.Apprise`` for outbound notifications.

    Lifecycle:
        1. ``__init__`` — creates a fresh ``Apprise()`` instance.
        2. ``add_channel(url)`` — registers one or more Apprise URLs.
        3. ``notify(message, ...)`` — sends to all configured channels.

    Thread-safety: Apprise's ``Apprise()`` is not thread-safe for concurrent
    ``add()`` calls, but Odysseus bootstrap is sequential (single-threaded
    startup).  Once channels are added, ``async_notify`` is safe for concurrent
    sends.
    """

    def __init__(self) -> None:
        self._apobj: apprise.Apprise = apprise.Apprise()

    # ------------------------------------------------------------------
    # Channel management
    # ------------------------------------------------------------------

    def add_channel(self, url: str) -> bool:
        """Register a single Apprise channel URL.  Returns True on success."""
        try:
            result = self._apobj.add(url)
            if result:
                logger.info("Apprise: channel registered (%s…)", url[:40])
            else:
                logger.warning("Apprise: failed to add channel (%s…)", url[:40])
            return bool(result)
        except Exception:
            logger.exception("Apprise: exception adding channel (%s…)", url[:40])
            return False

    def add_channels(self, urls: list[str]) -> int:
        """Register multiple channel URLs.  Returns count of successful adds."""
        ok = 0
        for url in urls:
            if self.add_channel(url):
                ok += 1
        return ok

    @property
    def channel_count(self) -> int:
        """Number of registered (loaded) Apprise notification URLs."""
        return len(self._apobj)

    # ------------------------------------------------------------------
    # Notification
    # ------------------------------------------------------------------

    async def notify(
        self,
        message: str,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """Send a notification to all registered channels.

        Parameters
        ----------
        message:
            Body text.
        title:
            Optional title / subject line.
        tags:
            Optional tag list for channel-side filtering.

        Returns
        -------
        bool
            True if *at least one* channel delivered successfully.
        """
        if not self._apobj:
            logger.debug("Apprise: no channels configured, skipping notify")
            return False

        try:
            result = await self._apobj.async_notify(
                body=message,
                title=title,
                tag=tags or [],
            )
            if result:
                logger.info("Apprise: notification delivered")
            else:
                logger.warning("Apprise: notification failed (all channels)")
            return bool(result)
        except Exception:
            logger.exception("Apprise: exception during notify")
            return False

    # ------------------------------------------------------------------
    # Reset (useful for tests)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all channels.  Primarily for unit tests."""
        self._apobj = apprise.Apprise()
