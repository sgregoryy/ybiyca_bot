from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

class SubscriptionKeyboard:
    @staticmethod
    def plans(tariff_plans):
        builder = InlineKeyboardBuilder()
        
        for plan in tariff_plans:
            builder.add(InlineKeyboardButton(
                text=f"{plan.name} - {plan.price}₽", 
                callback_data=f"plan:{plan.id}"
            ))
        
        builder.adjust(1)
        return builder.as_markup()
    
    @staticmethod
    def subscribe_channel(channel_link: str):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Подписаться на канал", url=channel_link),
            InlineKeyboardButton(text="🔄 Я подписался, проверить", callback_data="check_subscription")
        )
        builder.adjust(1)
        return builder.as_markup()


class AdminKeyboard:
    @staticmethod
    def payment_approval(payment_id: int):
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_payment:{payment_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_payment:{payment_id}")
        )
        builder.adjust(2)
        return builder.as_markup()
    
    @staticmethod
    def admin_menu():
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin:statistics"),
            InlineKeyboardButton(text="📨 Рассылка", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="💰 Платежи", callback_data="admin:payments"),
            InlineKeyboardButton(text="📝 Управление тарифами", callback_data="admin:manage_tariffs")
        )
        builder.adjust(1)
        return builder.as_markup()
        
    @staticmethod
    def manage_tariffs_menu():
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(text="➕ Добавить тариф", callback_data="tariff:add"),
            InlineKeyboardButton(text="✏️ Редактировать тарифы", callback_data="tariff:list_edit"),
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back_to_menu")
        )
        builder.adjust(1)
        return builder.as_markup()