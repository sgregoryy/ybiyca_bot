from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union, List
import logging
from src.config import config

logger = logging.getLogger(__name__)

class AdminFilter(BaseFilter):
    def __init__(self):
        super().__init__()
        
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:
        if isinstance(message, Message):
            return message.from_user.id in config.telegram.admin_ids
        elif isinstance(message, CallbackQuery):
            return message.from_user.id in config.telegram.admin_ids
        return False