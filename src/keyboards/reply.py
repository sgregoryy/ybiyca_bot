from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from src.config import config

class MainKeyboard:
    @staticmethod
    def main_menu():
        builder = ReplyKeyboardBuilder()
        
        # Кнопка тарифов
        builder.add(KeyboardButton(text="💼 Тарифы"))
        
        # Кнопка подписок в зависимости от режима
        if config.channels.multi_channel_mode:
            builder.add(KeyboardButton(text="📺 Подписки"))
        else:
            builder.add(KeyboardButton(text="📺 Подписка"))
        
        # Кнопка информации
        builder.add(KeyboardButton(text="ℹ️ Информация"))
        
        builder.adjust(2, 1)
        return builder.as_markup(resize_keyboard=True)