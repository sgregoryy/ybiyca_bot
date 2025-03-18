from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from src.db.models import PaymentMethod, TariffPlan, Currency
from typing import List, Optional
from src.config import config


class SubscriptionKeyboard:
    @staticmethod
    def plans(tariff_plans):
        builder = InlineKeyboardBuilder()

        for plan in tariff_plans:
            builder.add(InlineKeyboardButton(text=f"{plan.name} - {plan.price}₽", callback_data=f"plan:{plan.id}"))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def payment_methods(payment_methods):
        """Создает клавиатуру со способами оплаты"""
        builder = InlineKeyboardBuilder()

        for method in payment_methods:
            if method.code == "manual":
                builder.add(
                    InlineKeyboardButton(
                        text="💳 Банковская карта (вручную)", callback_data=f"payment_method:{method.code}"
                    )
                )
            elif method.code == "youkassa":
                builder.add(
                    InlineKeyboardButton(
                        text="💳 Банковская карта (ЮKassa)", callback_data=f"payment_method:{method.code}"
                    )
                )
            elif method.code == "tinkoff":
                builder.add(
                    InlineKeyboardButton(
                        text="💳 Банковская карта (Tinkoff)", callback_data=f"payment_method:{method.code}"
                    )
                )
            elif method.code == "stars":
                builder.add(
                    InlineKeyboardButton(text="⭐️ Звезды Telegram", callback_data=f"payment_method:{method.code}")
                )
            else:
                builder.add(InlineKeyboardButton(text=method.name, callback_data=f"payment_method:{method.code}"))

        builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_plan_selection"))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def currencies(currencies: List[Currency], method_code: str, with_back: bool = True):
        """
        Создаёт клавиатуру для выбора валюты оплаты

        Args:
            currencies: список валют
            method_code: код метода оплаты
            with_back: добавлять ли кнопку назад

        Returns:
            Клавиатура для выбора валюты
        """
        builder = InlineKeyboardBuilder()

        for currency in currencies:
            builder.add(
                InlineKeyboardButton(
                    text=f"{currency.name} ({currency.symbol})",
                    callback_data=f"payment_currency:{method_code}:{currency.id}",
                )
            )

        if with_back:
            builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="payment_back_to_methods"))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def subscribe_channel(channel_link: str):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Подписаться на канал", url=channel_link),
            InlineKeyboardButton(text="🔄 Я подписался, проверить", callback_data="check_subscription"),
        )
        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def confirmation(confirm_callback: str, cancel_callback: str = "cancel_payment"):
        """
        Создаёт клавиатуру для подтверждения действия

        Args:
            confirm_callback: callback для кнопки подтверждения
            cancel_callback: callback для кнопки отмены

        Returns:
            Клавиатура для подтверждения
        """
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_callback),
            InlineKeyboardButton(text="❌ Отменить", callback_data=cancel_callback),
        )
        builder.adjust(2)
        return builder.as_markup()

    @staticmethod
    def back_to_tariffs():
        """
        Создаёт клавиатуру для возврата к тарифам

        Returns:
            Клавиатура для возврата к тарифам
        """
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="◀️ Назад к тарифам", callback_data="back_to_tariffs"))
        return builder.as_markup()

    @staticmethod
    def channels_list(channels_list, update_callback: str = "update_channel_subscriptions"):
        """
        Создаёт клавиатуру со списком каналов для подписки

        Args:
            channels_list: список информации о каналах
            update_callback: callback для обновления списка

        Returns:
            Клавиатура со списком каналов
        """
        builder = InlineKeyboardBuilder()

        for channel in channels_list:
            builder.add(InlineKeyboardButton(text=f"Подписаться на {channel['name']}", url=channel["invite_link"]))

        builder.add(InlineKeyboardButton(text="🔄 Обновить статус подписок", callback_data=update_callback))

        builder.adjust(1)
        return builder.as_markup()


class AdminKeyboard:
    @staticmethod
    def payment_approval(payment_id: int):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_payment:{payment_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_payment:{payment_id}"),
        )
        builder.adjust(2)
        return builder.as_markup()

    @staticmethod
    def admin_menu():
        builder = InlineKeyboardBuilder()

        builder.add(
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin:statistics"),
            InlineKeyboardButton(text="📨 Рассылка", callback_data="admin:broadcast"),
        )

        if config.admin.manage_tariffs_enabled:
            builder.add(InlineKeyboardButton(text="📝 Управление тарифами", callback_data="admin:manage_tariffs"))

        if config.admin.manage_channels_enabled and config.channels.multi_channel_mode:
            builder.add(InlineKeyboardButton(text="📺 Управление каналами", callback_data="admin:manage_channels"))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def manage_tariffs_menu():
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="➕ Добавить тариф", callback_data="tariff:add"),
            InlineKeyboardButton(text="✏️ Редактировать тарифы", callback_data="tariff:list_edit"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_menu"),
        )
        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def manage_channels_menu():
        """
        Создает клавиатуру для управления каналами

        Returns:
            Клавиатура для управления каналами
        """
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="➕ Добавить канал", callback_data="channel:add"),
            InlineKeyboardButton(text="✏️ Редактировать каналы", callback_data="channel:list_edit"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_menu"),
        )
        builder.adjust(1)
        return builder.as_markup()
