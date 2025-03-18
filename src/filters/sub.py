from aiogram.types import CallbackQuery
from aiogram.filters import BaseFilter
from aiogram.utils.i18n import lazy_gettext as __
from src.config import config

class SubscriptionFilter(BaseFilter):
    def __init__(self):
        super().__init__()
        
    async def __call__(self, callback: CallbackQuery):
        bot = callback.bot
        try:
            member = await bot.get_chat_member(chat_id=config.telegram.sponsor_channel_id, user_id=callback.from_user.id)
            if member.status not in ['left', 'kicked', 'banned']:
                return  True
            else:
                await bot.send_message(
                    chat_id=callback.from_user.id,
                    text=__("Для использования бота необходимо подписаться на канал")
                )
                return False
        except Exception:
            return False