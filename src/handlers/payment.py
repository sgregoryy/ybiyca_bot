from aiogram import Router, F
from aiogram.types import CallbackQuery
from src.db.DALS.payment import PaymentDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.config import config
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("approve_payment:"))
async def approve_payment(callback: CallbackQuery):
    """Обработчик для подтверждения платежа администратором"""
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    payment_id = int(callback.data.split(":")[1])
    
    # Подтверждаем платеж
    result = await PaymentDAL.approve_payment(payment_id)
    
    if not result:
        await callback.answer("Платеж не найден", show_alert=True)
        return
    
    payment, user, plan, currency, payment_method = result
    
    # Создаем подписку
    subscription_result = await SubscriptionDAL.create_subscription(user.id, plan.id)
    
    if not subscription_result:
        await callback.answer("Ошибка при создании подписки", show_alert=True)
        return
    
    subscription, plan = subscription_result
    
    # Уведомляем пользователя
    await callback.bot.send_message(
        chat_id=user.user_id,
        text=(
            f"✅ <b>Ваш платеж подтвержден!</b>\n\n"
            f"Вы успешно оформили подписку на тариф: {plan.name}\n"
            f"Срок действия: до {subscription.end_date.strftime('%d.%m.%Y')}\n"
            f"Спасибо за покупку!"
        ), parse_mode='HTML'
    )
    
    await callback.answer("Платеж подтвержден и подписка активирована", show_alert=True)
    
    # Обновляем сообщение
    await callback.message.edit_caption(
        caption=(
            f"✅ <b>Платеж подтвержден</b>\n\n"
            f"👤 Пользователь: {user.full_name} (@{user.username})\n"
            f"💰 Сумма: {payment.amount} {currency.symbol}\n"
            f"💳 Способ оплаты: {payment_method.name}\n"
            f"📋 Тариф: {plan.name}\n"
            f"🆔 ID платежа: {payment.id}"
        ), parse_mode='HTML'
    )

@router.callback_query(F.data.startswith("reject_payment:"))
async def reject_payment(callback: CallbackQuery):
    """Обработчик для отклонения платежа администратором"""
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    payment_id = int(callback.data.split(":")[1])
    
    # Отклоняем платеж
    result = await PaymentDAL.reject_payment(payment_id)
    
    if not result:
        await callback.answer("Платеж не найден", show_alert=True)
        return
    
    payment, user, plan, currency, payment_method = result
    
    # Уведомляем пользователя
    await callback.bot.send_message(
        chat_id=user.user_id,
        text=(
            f"❌ <b>Ваш платеж отклонен</b>\n\n"
            f"К сожалению, ваш платеж на сумму {payment.amount} {currency.symbol} "
            f"за тариф \"{plan.name}\" был отклонен.\n"
            f"Пожалуйста, проверьте правильность оплаты или свяжитесь с администратором для уточнения деталей."
        ), parse_mode='HTML'
    )
    
    await callback.answer("Платеж отклонен", show_alert=True)
    
    # Обновляем сообщение
    await callback.message.edit_caption(
        caption=(
            f"❌ <b>Платеж отклонен</b>\n\n"
            f"👤 Пользователь: {user.full_name} (@{user.username})\n"
            f"💰 Сумма: {payment.amount} {currency.symbol}\n"
            f"💳 Способ оплаты: {payment_method.name}\n"
            f"📋 Тариф: {plan.name}\n"
            f"🆔 ID платежа: {payment.id}"
        ), parse_mode='HTML'
    )