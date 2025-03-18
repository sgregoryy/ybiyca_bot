import logging
from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.db.models import TariffPlan
from src.db.DALS.currency import CurrencyDAL
from src.db.DALS.user import UserDAL
from src.db.DALS.payment import PaymentDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.tariff import TariffDAL
from src.keyboards.reply import MainKeyboard

from src.config import config

logger = logging.getLogger(__name__)


async def create_invoice(amount: float, desc: str, payload: str, asset: str = "USDT"):
    if not config.payment.cryptobot_enabled or not config.payment.cryptobot:
        logger.error("CryptoBot payments are disabled or not initialized")
        return "error"

    try:
        invoice = await config.payment.cryptobot.create_invoice(
            asset=asset,
            amount=amount,
            description=desc,
            payload=payload,
        )

        if hasattr(invoice, "bot_invoice_url"):
            return invoice.bot_invoice_url
        else:
            logger.error(f"Error creating cryptobot invoice: {invoice}")
            return "error"
    except Exception as e:
        logger.exception(f"Exception creating cryptobot invoice: {e}")
        return "error"


async def process_crypto_payment(payload):
    try:
        logger.info(f"Processing cryptobot webhook: {payload}")

        if payload["status"] == "paid":
            custom_payload = payload["payload"]
            user_id_str, payment_id_str = custom_payload.split(":")

            try:
                user_id = int(user_id_str)
                payment_id = int(payment_id_str)

                payment_data = await PaymentDAL.get_payment_with_details(payment_id)
                if not payment_data:
                    logger.error(f"Payment {payment_id} not found")
                    return False

                payment, user, plan, currency = payment_data

                payment_result = await PaymentDAL.approve_payment(payment_id)

                if payment_result:

                    subscription_result = await SubscriptionDAL.create_subscription(user.id, plan.id)

                    if subscription_result:
                        subscription, plan = subscription_result

                        bot = Bot(token=config.telegram.token)
                        await bot.send_message(
                            chat_id=user.user_id,
                            text=(
                                f"✅ <b>Оплата через CryptoBot успешно подтверждена!</b>\n\n"
                                f"Тариф: <b>{plan.name}</b>\n"
                                f"Оплачено: <b>{payment.amount} {currency.symbol}</b>\n"
                                f"Дата окончания: <b>{subscription.end_date.strftime('%d.%m.%Y')}</b>\n\n"
                                f"Благодарим за оплату! Ваша подписка активирована."
                            ),
                            reply_markup=MainKeyboard.main_menu(),
                            parse_mode="HTML",
                        )

                        logger.info(f"Successfully processed payment for user {user.user_id}, amount: {payment.amount}")
                        return True
                    else:
                        logger.error(f"Failed to create subscription for user {user.user_id}")
                else:
                    logger.error(f"Failed to approve payment {payment_id}")
            except ValueError as e:
                logger.error(f"Error converting user_id or payment_id: {e}")
            except Exception as e:
                logger.exception(f"Error processing payment: {e}")
        else:
            logger.warning(f"Received unpaid invoice: {payload}")

        return False
    except Exception as e:
        logger.exception(f"Error processing cryptobot webhook: {e}")
        return False


async def cryptobot_payment_route(callback: CallbackQuery, plan: TariffPlan, default_currency, final_price):
    """
    Обработка платежа через CryptoBot

    Args:
        callback: Callback запрос
        state: Состояние FSM
        plan: Тарифный план
        payment_method: Метод оплаты
        default_currency: Валюта по умолчанию
        final_price: Финальная цена с учетом комиссии
    """
    if not config.payment.cryptobot_enabled or not config.payment.cryptobot:
        await callback.answer("Оплата через CryptoBot временно недоступна", show_alert=True)
        return

    user = await UserDAL.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=f"{callback.from_user.first_name} {callback.from_user.last_name or ''}",
    )

    currency = await CurrencyDAL.get_by_code("USDT")
    if not currency:
        currency = default_currency

    usdt_amount = round(final_price / 90, 2)

    payment_record = await PaymentDAL.create_payment(
        user_id=user.id, plan_id=plan.id, currency_id=currency.id, amount=usdt_amount, payment_method="cryptobot"
    )

    payload = f"{user.id}:{payment_record.id}"

    description = f"Оплата тарифа {plan.name}"

    payment_url = await create_invoice(amount=usdt_amount, desc=description, payload=payload)

    if payment_url == "error":
        await callback.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)

        await PaymentDAL.cancel_payment(payment_record.id)
        return

    await PaymentDAL.update_payment(payment_id=payment_record.id, external_id=payment_url)

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text=f"💰 Оплатить {usdt_amount} USDT", url=payment_url))

    builder.add(InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment"))

    builder.adjust(1)

    await callback.message.edit_text(
        f"💰 <b>Оплата через CryptoBot</b>\n\n"
        f"Тариф: <b>{plan.name}</b>\n"
        f"Сумма к оплате: <b>{usdt_amount} USDT</b>\n\n"
        f"Для оплаты нажмите на кнопку ниже. После успешной оплаты подписка будет активирована автоматически.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
