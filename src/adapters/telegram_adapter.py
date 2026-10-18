"""
Telegram adapter pour Channel Gateway.
Utilise python-telegram-bot (pip install python-telegram-bot).
"""

import logging
from collections.abc import Callable
from typing import Any

from src.channel_gateway import ChannelAdapter, ChannelType, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)


class TelegramAdapter(ChannelAdapter):
    """
    Adapter Telegram via Bot API officielle.
    Configure : TELEGRAM_BOT_TOKEN dans .env
    """

    def __init__(self, bot_token: str | None = None, default_chat_id: int | None = None):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id
        self._app = None

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.TELEGRAM

    async def send(self, message: OutboundMessage) -> bool:
        try:
            from telegram import Bot

            if not self.bot_token:
                return False

            chat_id = int(message.recipient_id) if message.recipient_id != "broadcast" else self.default_chat_id
            if not chat_id:
                return False

            bot = Bot(token=self.bot_token)
            await bot.send_message(chat_id=chat_id, text=message.content[:4096])  # Limite Telegram
            return True
        except ImportError:
            logger.warning("Telegram: pip install python-telegram-bot requis")
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
        return False

    async def start_listening(self, on_message: Callable[[InboundMessage], Any]) -> None:
        try:
            from telegram.ext import Application, MessageHandler, filters

            app = Application.builder().token(self.bot_token).build()
            self._app = app

            async def handle(update, context):
                msg = update.message
                if not msg:
                    return

                inbound = InboundMessage(
                    channel=ChannelType.TELEGRAM,
                    sender_id=str(msg.from_user.id),
                    sender_name=msg.from_user.first_name or "",
                    content=msg.text or "",
                    raw={"chat_id": str(msg.chat_id), "message_id": str(msg.message_id)},
                    reply_fn=lambda text: msg.reply_text(text[:4096]),
                )
                await on_message(inbound)

            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
            await app.run_polling(drop_pending_updates=True)
        except ImportError:
            logger.warning("Telegram adapter: pip install python-telegram-bot pour activer")
        except Exception as e:
            logger.error(f"Telegram start error: {e}")
