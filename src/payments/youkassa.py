import uuid
import logging
from typing import Optional, Dict, Tuple, Union

from src.config import config

from src.db.models import TariffPlan
from src.db.DALS.payment import PaymentDAL
from src.db.DALS.user import UserDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.currency import CurrencyDAL
from src.db.DALS.channel import ChannelDAL
from src.db.DALS.payment_method import PaymentMethodDAL

from datetime import datetime
from aiogram import Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from yookassa import Configuration, Payment

bot = Bot(token=config.telegram.token)

logger = logging.getLogger(__name__)


async def create_payment(
    amount: float, user_id: int, plan_id: int, email: str = None, description: str = "Оплата подписки"
) -> Optional[Dict]:
    """
    Создание платежа в YooKassa

    Args:
        amount: Сумма платежа
        user_id: ID пользователя в базе данных
        plan_id: ID тарифного плана
        email: Email пользователя (опционально)
        description: Описание платежа

    Returns:
        Данные для перенаправления на оплату или None в случае ошибки
    """
    try:
        Configuration.account_id = config.payment.youkassa_shop_id
        Configuration.secret_key = config.payment.youkassa_secret_key

        idempotence_key = str(uuid.uuid4())

        payment_data = {
            "amount": {"value": str(amount), "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": (
                    f"{config.webapp.webhook_base_url}/payments/youkassa/return"
                    if config.webapp.webhook_base_url
                    else "https://t.me/" + config.telegram.token.split(":")[0]
                ),
            },
            "capture": True,
            "description": description,
            "metadata": {"user_id": user_id, "plan_id": plan_id},
        }

        if email:
            payment_data["receipt"] = {
                "customer": {"email": email},
                "items": [
                    {
                        "description": description,
                        "quantity": "1",
                        "amount": {"value": str(amount), "currency": "RUB"},
                        "vat_code": 1,
                        "payment_subject": "service",
                        "payment_mode": "full_prepayment",
                    }
                ],
            }
        payment_response = Payment.create(payment_data, idempotence_key)

        if payment_response.confirmation and payment_response.confirmation.confirmation_url:
            return {
                "confirmation_url": payment_response.confirmation.confirmation_url,
                "payment_id": payment_response.id,
            }
        else:
            logger.error(f"No confirmation URL in YooKassa response: {payment_response}")
            return None

    except Exception as e:
        logger.error(f"Error creating YooKassa payment: {e}")
        return None


async def process_payment_notification(notification_data: dict) -> bool:
    """
    Обработка уведомления о платеже от YooKassa

    Args:
        notification_data: Данные уведомления

    Returns:
        True если платеж успешно обработан, False в противном случае
    """
    try:
        if notification_data.get("event") != "payment.succeeded":
            logger.info(f"Ignoring YooKassa event: {notification_data.get('event')}")
            return False

        payment_data = notification_data.get("object")
        if not payment_data:
            logger.error("No payment data in YooKassa notification")
            return False

        if payment_data.get("status") != "succeeded" or not payment_data.get("paid"):
            logger.info(f"YooKassa payment not succeeded: {payment_data}")
            return False

        metadata = payment_data.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_id = metadata.get("plan_id")

        if not user_id or not plan_id:
            logger.error(f"Missing user_id or plan_id in YooKassa payment metadata: {metadata}")
            return False

        user = await UserDAL.get_by_id(int(user_id))
        if not user:
            logger.error(f"User {user_id} not found")
            return False

        amount = float(payment_data.get("amount", {}).get("value", 0))
        payment_id = payment_data.get("id", "")

        payment = await PaymentDAL.get_by_external_id(payment_id)

        if payment:
            await PaymentDAL.update_payment(payment_id=payment.id, status="approved", processed_at=datetime.now())
        else:

            currency = await CurrencyDAL.get_by_code("RUB")
            if not currency:
                logger.error("RUB currency not found")
                return False

            payment_method = await PaymentMethodDAL.get_by_code("youkassa")
            if not payment_method:
                logger.error("youkassa payment method not found")
                return False

            payment = await PaymentDAL.create_payment(
                user_id=int(user_id),
                plan_id=int(plan_id),
                currency_id=currency.id,
                amount=amount,
                payment_method_id=payment_method.id,
                external_id=payment_id,
                status="approved",
            )

        subscription_result = await SubscriptionDAL.create_subscription(int(user_id), int(plan_id))

        if subscription_result:
            subscription, plan = subscription_result
            channel = await ChannelDAL.get_by_id(plan.channel_id)

            try:
                if channel:
                    await bot.unban_chat_member(chat_id=channel.channel_id, user_id=user.user_id)

                await bot.send_message(
                    chat_id=user.user_id,
                    text=(
                        f"✅ <b>Оплата успешно подтверждена!</b>\n\n"
                        f"Тариф: <b>{plan.name}</b>\n"
                        f"Сумма: <b>{amount}₽</b>\n"
                        f"Дата окончания: <b>{subscription.end_date.strftime('%d.%m.%Y')}</b>\n\n"
                        f"Благодарим за оплату! Ваша подписка активирована."
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🔗 Вступить в канал", url=channel.invite_link)]
                        ]
                    ) if channel else None,
                    parse_mode="HTML",
                )

            except Exception as e:
                logger.error(f"Error sending notification to user {user.user_id}: {e}")

            logger.info(f"Successfully processed YooKassa payment {payment_id} for user {user.user_id}")
            return True
        else:
            logger.error(f"Failed to create subscription for YooKassa payment {payment_id}")
            return False

    except Exception as e:
        logger.error(f"Error processing YooKassa payment notification: {e}")
        return False


async def yookassa_payment_route(
    event: Union[CallbackQuery, Message],
    plan: TariffPlan,
    default_currency,
    final_price,
    email: Optional[str] = None
):
    user = await UserDAL.get_or_create(
        telegram_id=event.from_user.id,
        username=event.from_user.username,
        full_name=f"{event.from_user.first_name} {event.from_user.last_name or ''}",
    )

    payment_method = await PaymentMethodDAL.get_by_code("youkassa")
    if not payment_method:
        logger.error("youkassa payment method not found")
        if isinstance(event, CallbackQuery):
            await event.answer("Ошибка: метод оплаты не найден.", show_alert=True)
        else:
            await event.answer("Ошибка: метод оплаты не найден.")
        return

    payment_record = await PaymentDAL.create_payment(
        user_id=user.id, plan_id=plan.id, currency_id=default_currency.id, amount=final_price, payment_method_id=payment_method.id
    )

    payment = await create_payment(
        amount=final_price,
        user_id=event.from_user.id,
        plan_id=plan.id,
        email=email,
        description=f"Оплата тарифа {plan.name}",
    )

    if not payment:
        logger.error("Error creating YouKassa payment: payment is None")
        if isinstance(event, CallbackQuery):
            await event.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)
        else:
            await event.answer("Ошибка при создании платежа. Попробуйте позже.")
        return

    if payment.get("payment_id"):
        await PaymentDAL.update_payment(payment_id=payment_record.id, external_id=payment["payment_id"])

    builder = InlineKeyboardBuilder()

    if payment.get("confirmation_url"):
        payment_url = payment["confirmation_url"]
        builder.add(InlineKeyboardButton(text=f"💰 Оплатить {final_price}₽", url=payment_url))
    else:
        logger.error(f"Error creating YouKassa payment: {payment}")
        if isinstance(event, CallbackQuery):
            await event.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)
        else:
            await event.answer("Ошибка при создании платежа. Попробуйте позже.")
        return

    builder.add(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment"))

    builder.adjust(1)

    # Отправляем сообщение в зависимости от типа события
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(
            f"💰 <b>Оплата через ЮKassa</b>\n\n"
            f"Тариф: <b>{plan.name}</b>\n"
            f"Сумма к оплате: <b>{final_price}₽</b>\n\n"
            f"Для оплаты нажмите на кнопку ниже. После успешной оплаты подписка будет активирована автоматически.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    else:
        await event.answer(
            f"💰 <b>Оплата через ЮKassa</b>\n\n"
            f"Тариф: <b>{plan.name}</b>\n"
            f"Сумма к оплате: <b>{final_price}₽</b>\n\n"
            f"Для оплаты нажмите на кнопку ниже. После успешной оплаты подписка будет активирована автоматически.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
