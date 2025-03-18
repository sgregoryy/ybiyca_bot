import logging
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Dict, List, Optional, Tuple

import aiohttp
from fastapi import HTTPException
from src.db.models import TariffPlan
from src.config import config

from src.db.DALS.payment import PaymentDAL
from src.db.DALS.user import UserDAL
from src.db.DALS.subscription import SubscriptionDAL
from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)


def get_token(data: dict) -> str:
    """Генерация токена для запроса"""
    data_sorted = sorted(data.keys())
    token_concat = "".join(str(data[field]) for field in data_sorted)
    return sha256(token_concat.encode()).hexdigest()


async def create_payment(
    amount: float, order_id: int, email: str, user_id: int, plan_id: int, description: str = "Оплата подписки"
) -> Optional[Dict]:
    """
    Создание платежа в Tinkoff

    Args:
        amount: Сумма платежа
        order_id: ID заказа/платежа
        email: Email пользователя
        user_id: ID пользователя в базе данных
        plan_id: ID тарифного плана
        description: Описание платежа

    Returns:
        Данные для перенаправления на оплату или None в случае ошибки
    """
    if not config.payment.tinkoff_enabled:
        logger.error("Tinkoff payment method is disabled")
        return None

    moscow_tz = timezone(timedelta(hours=3))
    redirect_due_date = datetime.now(moscow_tz) + timedelta(minutes=10)
    redirect_due_date_str = redirect_due_date.strftime("%Y-%m-%dT%H:%M:%S+03:00")

    amount_kopeks = int(amount * 100)

    token_data = {
        "TerminalKey": config.payment.tinkoff_terminal_key,
        "Amount": amount_kopeks,
        "OrderId": str(order_id),
        "Description": description,
        "Password": config.payment.tinkoff_secret_key,
        "RedirectDueDate": redirect_due_date_str,
    }

    payment_items = [
        {
            "Name": f"Подписка на {description}",
            "Price": amount_kopeks,
            "Quantity": 1,
            "Amount": amount_kopeks,
            "Tax": "none",
            "PaymentMethod": "full_prepayment",
            "PaymentObject": "service",
            "MeasurementUnit": "0",
        }
    ]

    data = {
        "TerminalKey": config.payment.tinkoff_terminal_key,
        "Amount": amount_kopeks,
        "OrderId": str(order_id),
        "Description": description,
        "Password": config.payment.tinkoff_secret_key,
        "RedirectDueDate": redirect_due_date_str,
        "Receipt": {"FfdVersion": "1.2", "Email": email, "Taxation": "patent", "Items": payment_items},
    }

    token = get_token(token_data)
    data["Token"] = token

    try:

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url="https://securepay.tinkoff.ru/v2/Init", json=data, headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    result = await response.json()

                    if result.get("Status") == "NEW" and result.get("Success"):
                        logger.info(f"Tinkoff payment created: {result}")
                        return result
                    else:
                        logger.error(f"Failed to create Tinkoff payment: {result}")
                        return None
                else:
                    logger.error(f"Error response from Tinkoff: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error creating Tinkoff payment: {e}")
        return None


def get_token_verify(data: dict) -> str:
    """Генерация токена для проверки подписи уведомления"""

    formatted_data = {
        "TerminalKey": str(data.get("TerminalKey", "")),
        "OrderId": str(data.get("OrderId", "")),
        "Success": "true" if data.get("Success") else "false",
        "Status": str(data.get("Status", "")),
        "PaymentId": str(data.get("PaymentId", "")),
        "ErrorCode": str(data.get("ErrorCode", "")),
        "Amount": str(data.get("Amount", "")),
        "CardId": str(data.get("CardId", "")),
        "Pan": str(data.get("Pan", "")),
        "ExpDate": str(data.get("ExpDate", "")),
        "Password": config.payment.tinkoff_secret_key,
    }

    sorted_keys = sorted(formatted_data.keys())

    values_concat = ""
    for key in sorted_keys:
        if key in formatted_data and formatted_data[key]:
            values_concat += formatted_data[key]

    token = sha256(values_concat.encode()).hexdigest()
    return token


async def verify_notification(data: dict) -> bool:
    """
    Проверка подписи уведомления от Tinkoff

    Args:
        data: Данные уведомления

    Returns:
        True если подпись верна, False в противном случае
    """
    received_token = data.get("Token")
    if not received_token:
        logger.error("Token missing in Tinkoff notification")
        return False

    calculated_token = get_token_verify(data)
    if received_token != calculated_token:
        logger.error(f"Tinkoff token mismatch. Received: {received_token}, Calculated: {calculated_token}")
        return False

    return True


async def process_payment_notification(notification_data: dict) -> bool:
    """
    Обработка уведомления о платеже от Tinkoff

    Args:
        notification_data: Данные уведомления

    Returns:
        True если платеж успешно обработан, False в противном случае
    """
    try:

        if not await verify_notification(notification_data):
            logger.error("Invalid Tinkoff notification signature")
            return False

        order_id = int(notification_data.get("OrderId", 0))
        payment_id = notification_data.get("PaymentId", "")
        status = notification_data.get("Status", "")
        success = notification_data.get("Success", False)

        logger.info(f"Processing Tinkoff payment notification: OrderId={order_id}, Status={status}, Success={success}")

        if success and status == "CONFIRMED":

            payment = await PaymentDAL.get_by_id(order_id)

            if not payment:
                logger.error(f"Payment {order_id} not found")
                return False

            await PaymentDAL.update_payment(
                payment_id=order_id, external_id=payment_id, status="approved", processed_at=datetime.now()
            )

            payment_details = await PaymentDAL.get_payment_with_details(order_id)
            if not payment_details:
                logger.error(f"Payment details not found for {order_id}")
                return False

            payment, user, plan, currency = payment_details

            subscription_result = await SubscriptionDAL.create_subscription(user.id, plan.id)

            if subscription_result:
                subscription, plan = subscription_result

                try:
                    from aiogram import Bot

                    bot = Bot(token=config.telegram.token)

                    await bot.send_message(
                        chat_id=user.user_id,
                        text=(
                            f"✅ <b>Оплата успешно подтверждена!</b>\n\n"
                            f"Тариф: <b>{plan.name}</b>\n"
                            f"Сумма: <b>{payment.amount}₽</b>\n"
                            f"Дата окончания: <b>{subscription.end_date.strftime('%d.%m.%Y')}</b>\n\n"
                            f"Благодарим за оплату! Ваша подписка активирована."
                        ),
                        parse_mode="HTML",
                    )

                    await bot.session.close()

                except Exception as e:
                    logger.error(f"Error sending notification to user {user.user_id}: {e}")

                logger.info(f"Successfully processed Tinkoff payment {order_id} for user {user.user_id}")
                return True
            else:
                logger.error(f"Failed to create subscription for payment {order_id}")
                return False
        else:
            logger.info(f"Tinkoff payment {order_id} not confirmed: Status={status}, Success={success}")
            return False

    except Exception as e:
        logger.error(f"Error processing Tinkoff payment notification: {e}")
        return False


async def tinkoff_payment_route(callback: CallbackQuery, plan: TariffPlan, default_currency, final_price):
    """
    Обработка платежа через Тинькофф

    Args:
        callback: Callback запрос
        state: Состояние FSM
        plan: Тарифный план
        payment_method: Метод оплаты
        default_currency: Валюта по умолчанию
        final_price: Финальная цена с учетом комиссии
    """
    if not config.payment.tinkoff_enabled:
        await callback.answer("Оплата через Тинькофф временно недоступна", show_alert=True)
        return

    payment_record = await PaymentDAL.create_payment(
        user_id=callback.from_user.id,
        plan_id=plan.id,
        currency_id=default_currency.id,
        amount=final_price,
        payment_method="tinkoff",
    )

    description = f"Оплата тарифа {plan.name}"

    payment_data = await create_payment(
        amount=final_price, user_id=callback.from_user.id, plan_id=plan.id, description=description
    )

    if not payment_data:
        await callback.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)

        await PaymentDAL.cancel_payment(payment_record.id)
        return

    payment_url = payment_data.get("PaymentURL")
    if not payment_url:
        await callback.answer("Ошибка при получении ссылки на оплату", show_alert=True)

        await PaymentDAL.cancel_payment(payment_record.id)
        return

    payment_id = payment_data.get("PaymentId")
    if payment_id:
        await PaymentDAL.update_payment(payment_id=payment_record.id, external_id=str(payment_id))

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text=f"💰 Оплатить {final_price}₽", url=payment_url))

    builder.add(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment"))

    builder.adjust(1)

    await callback.message.edit_text(
        f"💰 <b>Оплата через Тинькофф</b>\n\n"
        f"Тариф: <b>{plan.name}</b>\n"
        f"Сумма к оплате: <b>{final_price}₽</b>\n\n"
        f"Для оплаты нажмите на кнопку ниже. После успешной оплаты подписка будет активирована автоматически.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
