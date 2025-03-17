from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

class MainKeyboard:
    @staticmethod
    def main_menu():
        builder = ReplyKeyboardBuilder()
        builder.add(
            KeyboardButton(text="💼 Тарифы"),
            KeyboardButton(text="👤 Мой профиль"),
            KeyboardButton(text="ℹ️ Информация")
        )
        builder.adjust(2, 1)
        return builder.as_markup(resize_keyboard=True)