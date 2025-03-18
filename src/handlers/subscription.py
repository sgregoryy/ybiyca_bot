from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from payments import youkassa
from src.db.models import TariffPlan
from src.keyboards.inline import SubscriptionKeyboard
from src.keyboards.reply import MainKeyboard
from src.utils.states import PaymentStates
from src.utils.channel_access import get_user_channel_invites, check_and_invite_to_channels
from src.db.DALS.user import UserDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.tariff import TariffDAL
from src.db.DALS.payment import PaymentDAL
from src.db.DALS.payment_method import PaymentMethodDAL
from src.db.DALS.currency import CurrencyDAL
from src.payments.cryptobot import cryptobot_payment_route
from src.payments.tinkoff import tinkoff_payment_route
from src.payments.youkassa import yookassa_payment_route
from src.payments.stars import process_stars_payment

from src.keyboards.inline import AdminKeyboard
from src.config import config

from src.payments import tinkoff, cryptobot

import logging

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "💼 Тарифы")
async def show_plans(message: Message):
    tariff_plans = await TariffDAL.get_active_plans()

    plans_text = "📋 Выберите подходящий тарифный план:\n\n"

    for plan in tariff_plans:
        plans_text += f"<b>{plan.name}</b> - {plan.price}₽\n"

    await message.answer(plans_text, reply_markup=SubscriptionKeyboard.plans(tariff_plans), parse_mode="HTML")


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: CallbackQuery):
    tariff_plans = await TariffDAL.get_active_plans()

    plans_text = "📋 Выберите подходящий тарифный план:\n\n"

    for plan in tariff_plans:
        plans_text += f"<b>{plan.name}</b> - {plan.price}₽\n"

    await callback.message.edit_text(
        plans_text, reply_markup=SubscriptionKeyboard.plans(tariff_plans), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"))
async def process_plan_selection(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split(":")[1])

    plan = await TariffDAL.get_by_id(plan_id)

    if not plan:
        await callback.answer("Тарифный план не найден", show_alert=True)
        return

    payment_methods = await PaymentMethodDAL.get_active_methods()

    enabled_methods = []
    for method in payment_methods:
        if method.code == "manual" and config.payment.manual_payment_enabled:
            enabled_methods.append(method)
        elif method.code == "youkassa" and config.payment.youkassa_enabled:
            enabled_methods.append(method)
        elif method.code == "tinkoff" and config.payment.tinkoff_enabled:
            enabled_methods.append(method)
        elif method.code == "cryptobot" and config.payment.cryptobot_enabled:
            enabled_methods.append(method)

    if not enabled_methods:
        await callback.answer("В данный момент оплата недоступна. Попробуйте позже.", show_alert=True)
        return

    await state.set_state(PaymentStates.waiting_for_payment_method)
    await state.update_data(selected_plan_id=plan_id)

    if len(enabled_methods) > 1:
        methods_text = (
            f"Вы выбрали тариф: <b>{plan.name}</b>\n\n"
            f"Сумма к оплате: <b>{plan.price}₽</b>\n\n"
            f"Выберите способ оплаты:"
        )

        await callback.message.edit_text(
            methods_text, reply_markup=SubscriptionKeyboard.payment_methods(enabled_methods), parse_mode="HTML"
        )
    else:
        payment_method = enabled_methods[0]
        await process_payment_method(callback, state, payment_method.code)

    await callback.answer()


@router.callback_query(F.data.startswith("payment_method:"))
async def handle_payment_method_selection(callback: CallbackQuery, state: FSMContext):
    method_code = callback.data.split(":")[1]
    await process_payment_method(callback, state, method_code)


async def process_payment_method(callback: CallbackQuery, state: FSMContext, method_code: str):
    """
    Обрабатывает выбор метода оплаты

    Args:
        callback: Callback query
        state: FSM context
        method_code: Код метода оплаты
    """
    data = await state.get_data()
    plan_id = data.get("selected_plan_id")

    plan = await TariffDAL.get_by_id(plan_id)

    if not plan:
        await callback.answer("Тарифный план не найден", show_alert=True)
        await state.clear()
        return

    payment_method = await PaymentMethodDAL.get_by_code(method_code)

    if not payment_method:
        await callback.answer("Метод оплаты не найден", show_alert=True)
        return

    default_currency = await PaymentMethodDAL.get_default_currency(payment_method.id)

    if not default_currency:
        await callback.answer("Ошибка: валюта для метода оплаты не найдена", show_alert=True)
        return

    await state.update_data(selected_method_id=payment_method.id, selected_currency_id=default_currency.id)

    final_price = await PaymentMethodDAL.calculate_price_with_method(plan.price, payment_method.id)

    if method_code == "manual":
        await process_manual_payment(callback, state, plan, payment_method, default_currency, final_price)
    elif method_code == "youkassa":
        await yookassa_payment_route(callback, state, plan, payment_method, default_currency, final_price)
    elif method_code == "tinkoff":
        await tinkoff_payment_route(callback, state, plan, payment_method, default_currency, final_price)
    elif method_code == "cryptobot":
        await cryptobot_payment_route(callback, state, plan, payment_method, default_currency, final_price)
    elif method_code == "stars":
        await process_stars_payment(callback, state)

    await callback.answer()


async def process_manual_payment(
    callback: CallbackQuery, state: FSMContext, plan: TariffPlan, payment_method, currency, final_price
):
    await state.set_state(PaymentStates.waiting_for_payment_screenshot)

    payment_text = (
        f"Вы выбрали тариф: <b>{plan.name}</b>\n\n"
        f"Сумма к оплате: <b>{final_price} {currency.symbol}</b>\n\n"
        f"Для оплаты переведите указанную сумму на следующие реквизиты:\n"
        f"💳 <b>Номер карты:</b> {config.payment.manual_card_number}\n"
        f"👤 <b>Получатель:</b> {config.payment.manual_recipient_name}\n\n"
        f"После оплаты, отправьте скриншот или фото чека об оплате.\n"
        f"Ваша заявка будет обработана администратором."
    )

    await callback.message.edit_text(
        payment_text, reply_markup=SubscriptionKeyboard.back_to_tariffs(), parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment_process(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get("payment_id")

    if payment_id:
        await PaymentDAL.cancel_payment(payment_id)

    await state.clear()

    await back_to_tariffs(callback)


@router.message(PaymentStates.waiting_for_payment_screenshot, F.photo)
async def process_payment_screenshot(message: Message, state: FSMContext):
    state_data = await state.get_data()
    plan_id = state_data.get("selected_plan_id")
    payment_method_id = state_data.get("selected_method_id")
    currency_id = state_data.get("selected_currency_id")

    file_id = message.photo[-1].file_id

    user = await UserDAL.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}",
    )

    plan = await TariffDAL.get_by_id(plan_id)

    if not plan:
        await message.answer("Ошибка: тарифный план не найден")
        await state.clear()
        return

    payment_method = await PaymentMethodDAL.get_by_id(payment_method_id)

    if not payment_method:
        await message.answer("Ошибка: метод оплаты не найден")
        await state.clear()
        return

    currency = await CurrencyDAL.get_by_id(currency_id)

    if not currency:
        await message.answer("Ошибка: валюта не найдена")
        await state.clear()
        return

    final_price = await PaymentMethodDAL.calculate_price_with_method(plan.price, payment_method.id)

    payment = await PaymentDAL.create_payment(
        user_id=user.id,
        plan_id=plan.id,
        payment_method_id=payment_method.id,
        currency_id=currency.id,
        amount=final_price,
        screenshot_file_id=file_id,
    )

    await state.clear()

    await message.answer(
        "✅ Спасибо! Ваша заявка принята и будет обработана администратором в ближайшее время.",
        reply_markup=MainKeyboard.main_menu(),
    )

    for admin_id in config.telegram.admin_ids:
        try:

            await message.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=(
                    f"🔔 <b>Новая заявка на оплату</b>\n\n"
                    f"👤 Пользователь: {message.from_user.full_name} (@{message.from_user.username})\n"
                    f"💰 Сумма: {final_price} {currency.symbol}\n"
                    f"📋 Тариф: {plan.name}\n"
                    f"💳 Способ оплаты: {payment_method.name}\n"
                    f"🆔 ID платежа: {payment.id}"
                ),
                reply_markup=AdminKeyboard.payment_approval(payment.id),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")


@router.message(F.text.in_(["📺 Подписка", "📺 Подписки"]))
async def show_subscriptions(message: Message):
    user = await UserDAL.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}",
    )

    subscription_data = await SubscriptionDAL.get_by_telegram_id(message.from_user.id)

    if subscription_data:
        subscription, plan, _ = subscription_data

        subscribed_channels, need_to_subscribe_channels = await check_and_invite_to_channels(
            message.bot, message.from_user.id
        )

        subscription_text = (
            f"📺 <b>Ваша подписка</b>\n\n"
            f"📅 Тариф: {plan.name}\n"
            f"⏱ Действует до: {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
        )

        if subscribed_channels or need_to_subscribe_channels:
            subscription_text += f"📺 <b>Доступные каналы:</b>\n"

            if subscribed_channels:
                subscription_text += "\n✅ <b>Вы уже подписаны:</b>\n"
                for i, channel in enumerate(subscribed_channels, 1):
                    subscription_text += f"{i}. {channel['name']}\n"

            if need_to_subscribe_channels:
                subscription_text += "\n❗️ <b>Необходимо подписаться:</b>\n"
                for i, channel in enumerate(need_to_subscribe_channels, 1):
                    subscription_text += f"{i}. {channel['name']}\n"

        await message.answer(subscription_text, parse_mode="HTML")

        if need_to_subscribe_channels:
            builder = InlineKeyboardBuilder()

            for channel in need_to_subscribe_channels:
                builder.add(InlineKeyboardButton(text=f"Подписаться на {channel['name']}", url=channel["invite_link"]))

            builder.add(
                InlineKeyboardButton(text="🔄 Обновить статус подписок", callback_data="update_channel_subscriptions")
            )

            builder.adjust(1)

            await message.answer(
                "Для получения полного доступа, пожалуйста, подпишитесь на все доступные каналы:",
                reply_markup=builder.as_markup(),
            )
    else:
        subscription_text = (
            f"📺 <b>У вас нет активной подписки</b>\n\n"
            f"Нажмите на кнопку '💼 Тарифы', чтобы выбрать подходящий тариф"
        )

        await message.answer(subscription_text, parse_mode="HTML")


@router.callback_query(F.data == "update_channel_subscriptions")
async def update_channel_subscriptions(callback: CallbackQuery):
    subscribed_channels, need_to_subscribe_channels = await check_and_invite_to_channels(
        callback.bot, callback.from_user.id
    )

    if not need_to_subscribe_channels:
        await callback.message.edit_text("✅ Отлично! Вы подписаны на все доступные каналы.")
    else:
        text = "Для получения полного доступа, пожалуйста, подпишитесь на все доступные каналы:\n\n"

        for i, channel in enumerate(need_to_subscribe_channels, 1):
            text += f"{i}. {channel['name']}\n"

        builder = InlineKeyboardBuilder()

        for channel in need_to_subscribe_channels:
            builder.add(InlineKeyboardButton(text=f"Подписаться на {channel['name']}", url=channel["invite_link"]))

        builder.add(
            InlineKeyboardButton(text="🔄 Обновить статус подписок", callback_data="update_channel_subscriptions")
        )

        builder.adjust(1)

        await callback.message.edit_text(text, reply_markup=builder.as_markup())

    await callback.answer()


@router.message(F.text == "ℹ️ Информация")
async def show_info(message: Message):
    info_text = (
        (
            "ℹ️ <b>О боте</b>\n\n"
            "Этот бот позволяет оформить подписку на наши каналы.\n\n"
            "📋 <b>Доступные команды:</b>\n"
            "/start - Запустить бота\n"
            "💼 Тарифы - Просмотр доступных тарифов\n"
            "📺 Подписки - Информация о ваших подписках\n\n"
        )
        if config.channels.multi_channel_mode
        else (
            "ℹ️ <b>О боте</b>\n\n"
            "Этот бот позволяет оформить подписку на наш канал.\n\n"
            "📋 <b>Доступные команды:</b>\n"
            "/start - Запустить бота\n"
            "💼 Тарифы - Просмотр доступных тарифов\n"
            "📺 Подписка - Информация о вашей подписке\n\n"
        )
    )
    available_methods = []
    if config.payment.manual_payment_enabled:
        available_methods.append("💳 Банковская карта (ручная оплата)")
    if config.payment.youkassa_enabled:
        available_methods.append("💰 ЮKassa")
    if config.payment.tinkoff_enabled:
        available_methods.append("🏦 Tinkoff")
    if config.payment.cryptobot_enabled:
        available_methods.append("💎 CryptoBot (криптовалюта)")

    if available_methods:
        info_text += "<b>Доступные способы оплаты:</b>\n"
        for method in available_methods:
            info_text += f"- {method}\n"

    await message.answer(info_text, parse_mode="HTML")
