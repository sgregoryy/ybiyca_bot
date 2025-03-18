from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, SuccessfulPayment, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
import logging

from src.utils.states import PaymentStates
from src.db.DALS.user import UserDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.tariff import TariffDAL
from src.db.DALS.payment import PaymentDAL
from src.db.DALS.currency import CurrencyDAL
from src.config import config
from src.keyboards.reply import MainKeyboard

logger = logging.getLogger(__name__)

router = Router()

@router.callback_query(F.data == "payment_method:stars")
async def process_stars_payment(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора оплаты звездами"""
    # Получаем данные из состояния
    data = await state.get_data()
    plan_id = data.get("selected_plan_id")
    
    # Получаем тарифный план
    plan = await TariffDAL.get_by_id(plan_id)
    if not plan:
        await callback.answer("Тарифный план не найден", show_alert=True)
        return
    
    # Конвертируем цену в звезды (примерно 5 рублей = 1 звезда)
    stars_amount = int(plan.price / 5)
    
    # Создаем LabeledPrice для инвойса
    price = [LabeledPrice(
        label=plan.name,
        amount=stars_amount
    )]
    
    # Создаем payload для инвойса
    payload = f"stars:{plan_id}"
    
    # Отправляем инвойс для оплаты звездами
    await callback.message.answer_invoice(
        title="Подписка",
        description=f"Подписка на тариф: {plan.name}",
        currency="XTR",
        provider_token="",
        prices=price,
        payload=payload
    )
    
    # Удаляем предыдущее сообщение
    await callback.message.delete()
    
    await callback.answer()

@router.pre_checkout_query(lambda query: True)
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Проверка запроса на оплату"""
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def handle_successful_payment(message: Message):
    """Обработчик успешной оплаты"""
    payment_charge_id = message.successful_payment.telegram_payment_charge_id
    

    payment_type, plan_id = message.successful_payment.invoice_payload.split(':')

    if payment_type != "stars" or message.successful_payment.currency != "XTR":
        return

    user = await UserDAL.get_by_telegram_id(message.from_user.id)
    if not user:
        logger.error(f"Пользователь не найден: {message.from_user.id}")
        return

    plan = await TariffDAL.get_by_id(int(plan_id))
    if not plan:
        logger.error(f"Тарифный план не найден: {plan_id}")
        return

    
    currency = await CurrencyDAL.get_by_code("STARS")
    if not currency:
        # Если валюты нет, создаем её
        currency = await CurrencyDAL.create_currency(
            code="STARS",
            name="Telegram Stars",
            symbol="⭐",
            requires_manual_confirmation=False
        )
    
    # Создаем запись о платеже
    stars_amount = message.successful_payment.total_amount
    payment = await PaymentDAL.create_payment(
        user_id=user.id,
        plan_id=int(plan_id),
        currency_id=currency.id,
        amount=stars_amount,
        payment_method="stars",
        external_id=payment_charge_id,
        status="approved",
        processed_at=datetime.now()
    )
    
    subscription_result = await SubscriptionDAL.create_subscription(user.id, int(plan_id))
    
    if subscription_result:
        subscription, plan = subscription_result
        
        await message.answer(
            f"✅ <b>Оплата успешно подтверждена!</b>\n\n"
            f"Тариф: <b>{plan.name}</b>\n"
            f"Стоимость: <b>{stars_amount} {currency.symbol}</b>\n"
            f"Дата окончания: <b>{subscription.end_date.strftime('%d.%m.%Y')}</b>\n\n"
            f"Благодарим за оплату! Ваша подписка активирована.",
            parse_mode="HTML",
            reply_markup=MainKeyboard.main_menu()
        )
    else:
        await message.answer(
            "❌ Произошла ошибка при активации подписки. Пожалуйста, обратитесь к администратору."
        )