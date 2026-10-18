"""
Discord adapter pour Channel Gateway.
Utilise discord.py (pip install discord.py).
"""

import logging
from collections.abc import Callable
from typing import Any

from src.channel_gateway import ChannelAdapter, ChannelType, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)


class DiscordAdapter(ChannelAdapter):
    """
    Adapter Discord via Bot API officielle.
    Configure : DISCORD_BOT_TOKEN dans .env
    """

    def __init__(self, bot_token: str | None = None, default_channel_id: int | None = None):
        self.bot_token = bot_token
        self.default_channel_id = default_channel_id
        self._client = None

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.DISCORD

    async def send(self, message: OutboundMessage) -> bool:
        """Envoie un message Discord."""
        try:
            import discord

            if not self._client or not self.bot_token:
                logger.warning("Discord: client non initialisé ou token manquant")
                return False

            channel_id = int(message.recipient_id) if message.recipient_id != "broadcast" else self.default_channel_id
            if not channel_id:
                return False

            channel = self._client.get_channel(channel_id)
            if channel:
                await channel.send(message.content[:2000])  # Limite Discord
                return True
        except ImportError:
            logger.warning("Discord: pip install discord.py requis")
        except Exception as e:
            logger.error(f"Discord send error: {e}")
        return False

    async def start_listening(self, on_message: Callable[[InboundMessage], Any]) -> None:
        """Démarre le bot Discord en écoute."""
        try:
            import discord

            intents = discord.Intents.default()
            intents.message_content = True
            client = discord.Client(intents=intents)
            self._client = client

            @client.event
            async def on_message(msg):
                if msg.author == client.user:
                    return

                inbound = InboundMessage(
                    channel=ChannelType.DISCORD,
                    sender_id=str(msg.author.id),
                    sender_name=str(msg.author.name),
                    content=msg.content,
                    raw={"guild_id": str(msg.guild.id) if msg.guild else None, "channel_id": str(msg.channel.id)},
                    reply_fn=lambda text: msg.reply(text[:2000]),
                )
                await on_message(inbound)

            if self.bot_token:
                await client.start(self.bot_token)
        except ImportError:
            logger.warning("Discord adapter: pip install discord.py pour activer")
        except Exception as e:
            logger.error(f"Discord start error: {e}")
