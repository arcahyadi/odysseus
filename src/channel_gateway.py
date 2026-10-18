"""
Channel Gateway — Inbound bus + Outbound bus.
Ajouter un canal = ajouter un adapter. Pas toucher au cœur.

When ODYSSEUS_APPRISE=on, outbound routing is delegated to AppriseService
(services.notifications.apprise_service).  The ChannelAdapter protocol and
inbound path remain unchanged.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any
from src.app_context import app_context


logger = logging.getLogger(__name__)


class ChannelType(Enum):
    # Only the two real in-process channels. EMAIL/WEBHOOK were removed: they
    # had no adapter and duplicated the mature native email-poller and
    # webhook_manager subsystems (never delivered through this gateway).
    DISCORD = "discord"
    TELEGRAM = "telegram"


@dataclass
class InboundMessage:
    """Message entrant normalisé."""

    channel: ChannelType
    sender_id: str  # ID utilisateur dans le canal
    sender_name: str
    content: str
    raw: dict  # Payload original
    reply_fn: Callable | None = None  # Fonction pour répondre directement


@dataclass
class OutboundMessage:
    """Message sortant normalisé."""

    channel: ChannelType
    recipient_id: str
    content: str
    metadata: dict = None


class ChannelAdapter(ABC):
    """Interface abstraite pour tous les adapters."""

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType: ...

    @abstractmethod
    async def send(self, message: OutboundMessage) -> bool:
        """Envoie un message via ce canal. Retourne True si succès."""
        ...

    @abstractmethod
    async def start_listening(self, on_message: Callable[[InboundMessage], Any]) -> None:
        """Démarre l'écoute des messages entrants."""
        ...


# ------------------------------------------------------------------
# Kill-switch helper (module-level for easy import by channel_bootstrap)
# ------------------------------------------------------------------
_TRUTHY = {"on", "1", "true", "yes"}


def _apprise_kill_switch() -> bool:
    """Return True when ODYSSEUS_APPRISE env is truthy."""
    val = os.getenv("ODYSSEUS_APPRISE", "off").strip().lower()
    return val in _TRUTHY


def _get_apprise_service():
    """Lazy-import and cache the AppriseService singleton."""
    if not _apprise_kill_switch():
        return None
    try:
        from services.notifications.apprise_service import AppriseService

        svc = AppriseService()
        # Load channels from config if available
        try:
            from src.config import config as _cfg

            channels = _cfg.notification.apprise_channels
            if channels:
                svc.add_channels(channels)
        except Exception:
            logger.debug("Could not load APPRISE_CHANNELS from config")
        return svc
    except ImportError:
        logger.warning("Apprise not installed; falling back to legacy adapters")
        return None


class ChannelGateway:
    """
    Bus central : inbound (adapters → handler) + outbound (handler → adapters).

    When the ODYSSEUS_APPRISE kill-switch is ON, outbound messages are routed
    through AppriseService instead of the registered ChannelAdapter.  Inbound
    handling is always adapter-based (Apprise is outbound-only).
    """

    def __init__(self):
        self._adapters: dict[ChannelType, ChannelAdapter] = {}
        self._inbound_handler: Callable | None = None
        self._apprise_service = None  # lazy-init on first use

    @property
    def apprise_enabled(self) -> bool:
        """True when the ODYSSEUS_APPRISE kill-switch is ON."""
        return _apprise_kill_switch()

    def register_adapter(self, adapter: ChannelAdapter) -> None:
        """Enregistre un adapter. Remplace si déjà présent."""
        self._adapters[adapter.channel_type] = adapter
        logger.info(f"Channel Gateway: adapter {adapter.channel_type.value} enregistré")

    def set_inbound_handler(self, handler: Callable[[InboundMessage], Any]) -> None:
        """Définit le handler pour tous les messages entrants."""
        self._inbound_handler = handler

    async def send(self, message: OutboundMessage) -> bool:
        """Envoie via Apprise (kill-switch ON) ou l'adapter approprié (OFF)."""
        if self.apprise_enabled:
            return await self._send_via_apprise(message)

        adapter = self._adapters.get(message.channel)
        if not adapter:
            logger.warning(f"Pas d'adapter pour {message.channel}")
            return False
        return await adapter.send(message)

    async def _send_via_apprise(self, message: OutboundMessage) -> bool:
        """Route outbound message through AppriseService."""
        if self._apprise_service is None:
            self._apprise_service = _get_apprise_service()
        if self._apprise_service is None:
            logger.warning("Apprise kill-switch ON but service unavailable")
            return False
        tags = [message.channel.value]
        return await self._apprise_service.notify(
            message.content,
            title=f"{message.channel.value}:{message.recipient_id}",
            tags=tags,
        )

    async def broadcast(self, content: str, channels: list[ChannelType] = None) -> dict:
        """Broadcast vers plusieurs canaux."""
        targets = channels or list(self._adapters.keys())
        results = {}
        for ch in targets:
            adapter = self._adapters.get(ch)
            if adapter:
                # Broadcast sans recipient_id spécifique — chaque adapter gère son channel par défaut
                msg = OutboundMessage(channel=ch, recipient_id="broadcast", content=content)
                results[ch.value] = await adapter.send(msg)
        return results

    async def start_all(self) -> None:
        """Démarre tous les adapters en écoute."""
        tasks = []
        for adapter in self._adapters.values():
            if self._inbound_handler:
                tasks.append(adapter.start_listening(self._inbound_handler))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Singleton
app_context.caches.gateway_instance: ChannelGateway | None = None


def get_gateway() -> ChannelGateway:
    if app_context.caches.gateway_instance is None:
        app_context.caches.gateway_instance = ChannelGateway()
    return app_context.caches.gateway_instance
