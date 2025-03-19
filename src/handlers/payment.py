from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from src.db.DALS.channel import ChannelDAL
from src.filters.admin import AdminFilter
from src.db.DALS.payment import PaymentDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.config import config
import logging

router = Router()
logger = logging.getLogger(__name__)

router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

@router.callback_query(F.data.startswith("approve_payment:"))
async def approve_payment(callback: CallbackQuery):
    
    
    payment_id = int(callback.data.split(":")[1])
    logger.info(payment_id)
    result = await PaymentDAL.approve_payment(payment_id)
    
    if not result:
        await callback.answer("Платеж не найден", show_alert=True)
        return
    
    payment, user, plan, currency, payment_method = result
    
    subscription_result = await SubscriptionDAL.create_subscription(user.id, plan.id)
    
    if not subscription_result:
        await callback.answer("Ошибка при создании подписки", show_alert=True)
        return
    
    subscription, plan = subscription_result
    
    channel = await ChannelDAL.get_by_id(plan.channel_id)
    
    await callback.bot.send_message(
        chat_id=user.user_id,
        text=(
            f"✅ <b>Ваш платеж подтвержден!</b>\n\n"
            f"Вы успешно оформили подписку на тариф: {plan.name}\n"
            f"Срок действия: до {subscription.end_date.strftime('%d.%m.%Y')}\n"
            f"Спасибо за покупку!"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='Ссылка', url=channel.invite_link)]
            ]
        ),
        parse_mode='HTML'
    )
    
    await callback.answer("Платеж подтвержден и подписка активирована", show_alert=True)
    
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
    
    
    payment_id = int(callback.data.split(":")[1])
    
    result = await PaymentDAL.reject_payment(payment_id)
    
    if not result:
        await callback.answer("Платеж не найден", show_alert=True)
        return
    
    payment, user, plan, currency, payment_method = result
    
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