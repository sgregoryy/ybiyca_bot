from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from typing import Union, List

class AdminFilter(BaseFilter):
    def __init__(self, admin_ids: Union[int, List[int]]):
        self.admin_ids = admin_ids if isinstance(admin_ids, list) else [admin_ids]
    
    async def __call__(self, message: Union[Message, CallbackQuery]) -> bool:
        if isinstance(message, Message):
            return message.from_user.id in self.admin_ids
        elif isinstance(message, CallbackQuery):
            return message.from_user.id in self.admin_ids
        return False