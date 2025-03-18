from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import BaseFilter
from aiogram.utils.i18n import lazy_gettext as __
from typing import Union, Dict, Any
from src.keyboards.inline import SubscriptionKeyboard
from src.config import config
import logging

logger = logging.getLogger(__name__)

class SubscriptionFilter(BaseFilter):
    """
    Фильтр для проверки подписки пользователя на спонсорский канал.
    Используется только если config.telegram.require_subscription=True
    """
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:

        if not config.telegram.require_subscription:
            return True 

        if not config.telegram.sponsor_channel_id:
            return True

        if isinstance(event, Message):
            bot = event.bot
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            bot = event.bot
            user_id = event.from_user.id
        else:
            return False
            
        if user_id in config.telegram.admin_ids:
            return True
            
        try:
            member = await bot.get_chat_member(chat_id=config.telegram.sponsor_channel_id, user_id=user_id)
            if member.status not in ['left', 'kicked', 'banned']:
                return True
            else:
                if isinstance(event, Message):
                    await bot.send_message(
                        chat_id=user_id,
                        text=__("Для использования бота необходимо подписаться на канал"),
                        reply_markup=SubscriptionKeyboard.subscribe_channel(config.telegram.sponsor_channel_link)
                    )
                return False
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки: {e}")
            return True