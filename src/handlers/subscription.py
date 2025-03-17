from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
from src.keyboards.inline import SubscriptionKeyboard, AdminKeyboard
from src.keyboards.reply import MainKeyboard
from src.utils.states import PaymentStates
from src.db.DALS.user import UserDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.tariff import TariffDAL
from src.db.DALS.payment import PaymentDAL
from src.config import config
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "💼 Тарифы")
async def show_plans(message: Message):
    # Получаем все активные тарифы
    tariff_plans = await TariffDAL.get_active_plans()
    
    plans_text = "📋 Выберите подходящий тарифный план:\n\n"
    
    for plan in tariff_plans:
        plans_text += f"<b>{plan.name}</b> - {plan.price}₽\n"
    
    await message.answer(plans_text, reply_markup=SubscriptionKeyboard.plans(tariff_plans))

@router.callback_query(F.data.startswith("plan:"))
async def process_plan_selection(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split(":")[1])
    
    # Получаем информацию о тарифном плане
    plan = await TariffDAL.get_by_id(plan_id)
    
    if not plan:
        await callback.answer("Тарифный план не найден", show_alert=True)
        return
    
    await state.set_state(PaymentStates.waiting_for_payment_screenshot)
    await state.update_data(selected_plan_id=plan.id)
    
    payment_text = (
        f"Вы выбрали тариф: <b>{plan.name}</b>\n\n"
        f"Сумма к оплате: <b>{plan.price}₽</b>\n\n"
        f"Для оплаты переведите указанную сумму на следующие реквизиты:\n"
        f"💳 <b>Номер карты:</b> {config.payment.manual_card_number}\n"
        f"👤 <b>Получатель:</b> {config.payment.manual_recipient_name}\n\n"
        f"После оплаты, отправьте скриншот или фото чека об оплате.\n"
        f"Ваша заявка будет обработана администратором."
    )
    
    await callback.message.answer(payment_text)
    await callback.answer()

@router.message(PaymentStates.waiting_for_payment_screenshot, F.photo)
async def process_payment_screenshot(message: Message, state: FSMContext):
    state_data = await state.get_data()
    plan_id = state_data.get("selected_plan_id")
    
    file_id = message.photo[-1].file_id
    
    # Получаем или создаем пользователя
    user = await UserDAL.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}"
    )
    
    # Получаем тарифный план
    plan = await TariffDAL.get_by_id(plan_id)
    
    if not plan:
        await message.answer("Ошибка: тарифный план не найден")
        await state.clear()
        return

    # Создаем запись о платеже
    payment = await PaymentDAL.create_payment(
        user_id=user.id,
        plan_id=plan.id,
        amount=plan.price,
        screenshot_file_id=file_id,
        payment_method="manual"
    )
    
    await state.clear()
    
    await message.answer(
        "✅ Спасибо! Ваша заявка принята и будет обработана администратором в ближайшее время.",
        reply_markup=MainKeyboard.main_menu()
    )
    
    # Отправляем уведомление администраторам
    for admin_id in config.telegram.admin_ids:
        await message.bot.send_photo(
            chat_id=admin_id,
            photo=file_id,
            caption=(
                f"🔔 <b>Новая заявка на оплату</b>\n\n"
                f"👤 Пользователь: {message.from_user.full_name} (@{message.from_user.username})\n"
                f"💰 Сумма: {plan.price}₽\n"
                f"📋 Тариф: {plan.name}\n"
                f"🆔 ID платежа: {payment.id}"
            ),
            reply_markup=AdminKeyboard.payment_approval(payment.id)
        )

@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message):
    # Получаем или создаем пользователя
    user = await UserDAL.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}"
    )
    
    # Получаем активную подписку пользователя
    subscription_data = await SubscriptionDAL.get_by_telegram_id(message.from_user.id)
    
    if subscription_data:
        subscription, plan, _ = subscription_data
        
        profile_text = (
            f"👤 <b>Ваш профиль</b>\n\n"
            f"🆔 ID: {user.user_id}\n"
            f"👤 Имя: {user.full_name}\n\n"
            f"📋 <b>Ваша подписка:</b>\n"
            f"📅 Тариф: {plan.name}\n"
            f"⏱ Действует до: {subscription.end_date.strftime('%d.%m.%Y')}"
        )
    else:
        profile_text = (
            f"👤 <b>Ваш профиль</b>\n\n"
            f"🆔 ID: {user.user_id}\n"
            f"👤 Имя: {user.full_name}\n\n"
            f"📋 <b>У вас нет активной подписки</b>\n"
            f"Нажмите на кнопку '💼 Тарифы', чтобы выбрать подходящий тариф"
        )
    
    await message.answer(profile_text)

@router.message(F.text == "ℹ️ Информация")
async def show_info(message: Message):
    info_text = (
        "ℹ️ <b>О боте</b>\n\n"
        "Этот бот позволяет оформить подписку на наши услуги.\n\n"
        "📋 <b>Доступные команды:</b>\n"
        "/start - Запустить бота\n"
        "💼 Тарифы - Просмотр доступных тарифов\n"
        "👤 Мой профиль - Информация о вашей подписке\n\n"
        "По всем вопросам обращайтесь к @admin"
    )
    
    await message.answer(info_text)