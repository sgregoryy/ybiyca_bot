from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from src.filters.sub import SubscriptionFilter
from src.db.models import Channel, TariffPlan
from src.keyboards.inline import SubscriptionKeyboard
from src.keyboards.reply import MainKeyboard
from src.utils.states import PaymentStates
from src.utils.channel_access import check_user_channel_subscription, get_user_available_channel
from src.db.DALS.user import UserDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.tariff import TariffDAL
from src.db.DALS.channel import ChannelDAL
from src.db.DALS.payment import PaymentDAL
from src.db.DALS.payment_method import PaymentMethodDAL
from src.db.DALS.currency import CurrencyDAL
from src.payments.cryptobot import cryptobot_payment_route
from src.payments.tinkoff import tinkoff_payment_route
from src.payments.youkassa import yookassa_payment_route
from src.payments.stars import process_stars_payment

from src.keyboards.inline import AdminKeyboard
from src.config import config

import logging

router = Router()
logger = logging.getLogger(__name__)

if config.telegram.require_subscription:
    router.message.filter(SubscriptionFilter())
    router.callback_query.filter(SubscriptionFilter())

@router.message(F.text == "💼 Тарифы")
async def show_channels_for_subscription(message: Message):
    """Показывает доступные тарифы или список каналов для выбора"""
    channels = await ChannelDAL.get_active_channels()
    
    if not channels:
        await message.answer("В данный момент нет доступных каналов для подписки.")
        return
    
    if len(channels) == 1:
        channel = channels[0]
        tariffs = await TariffDAL.get_tariffs_by_channel(channel.id)
        
        if not tariffs:
            await message.answer("Для этого канала нет доступных тарифов.")
            return
        
        plans_text = f"📋 <b>Тарифы для канала {channel.name}</b>\n\n"
        
        # for plan in tariffs:
        #     plans_text += f"<b>{plan.name}</b> - {plan.price}₽\n"
        
        plans_text += "\nВыберите подходящий тарифный план:"
        
        builder = InlineKeyboardBuilder()
        
        for plan in tariffs:
            builder.add(InlineKeyboardButton(
                text=f"{plan.name} - {plan.price}₽",
                callback_data=f"plan:{plan.id}"
            ))
        
        builder.adjust(1)
        
        await message.answer(plans_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        return
    
    text = "📺 <b>Выберите канал для подписки:</b>\n\n"
    
    builder = InlineKeyboardBuilder()
    
    for channel in channels:
        builder.add(InlineKeyboardButton(
            text=channel.name,
            callback_data=f"select_channel:{channel.id}"
        ))
    
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("select_channel:"))
async def show_channel_tariffs(callback: CallbackQuery, c_id = None):
    """Показывает тарифы для выбранного канала"""
    if c_id:
        channel_id = int(c_id)
    else:
        channel_id = int(callback.data.split(":")[1])
    
    # Получаем информацию о канале
    channel = await ChannelDAL.get_by_id(channel_id)
    
    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return
    
    # Получаем тарифные планы для канала - теперь напрямую связанные с этим каналом
    tariffs = await TariffDAL.get_tariffs_by_channel(channel_id)
    
    if not tariffs:
        await callback.answer("Для этого канала нет доступных тарифов", show_alert=True)
        await callback.message.edit_text(
            "⚠️ Для выбранного канала нет доступных тарифов. Выберите другой канал.",
            reply_markup=InlineKeyboardBuilder().add(
                InlineKeyboardButton(text="◀️ Назад к каналам", callback_data="back_to_channels")
            ).as_markup()
        )
        return
    channels = await ChannelDAL.get_active_channels()
    if len(channels) == 1:
        channel = channels[0]
        tariffs = await TariffDAL.get_tariffs_by_channel(channel.id)
        
        if not tariffs:
            await callback.message.edit_text("Для этого канала нет доступных тарифов.")
            return
        
        plans_text = f"📋 <b>Тарифы для канала {channel.name}</b>\n\n"
        
        # for plan in tariffs:
        #     plans_text += f"<b>{plan.name}</b> - {plan.price}₽\n"
        
        plans_text += "\nВыберите подходящий тарифный план:"
        
        builder = InlineKeyboardBuilder()
        
        for plan in tariffs:
            builder.add(InlineKeyboardButton(
                text=f"{plan.name} - {plan.price}₽",
                callback_data=f"plan:{plan.id}"
            ))
        
        builder.adjust(1)
        
        await callback.message.edit_text(plans_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        return
    
    plans_text = f"📋 <b>Тарифы для канала {channel.name}</b>\n\n"
    
    for plan in tariffs:
        plans_text += f"<b>{plan.name}</b> - {plan.price}₽\n"
    
    plans_text += "\nВыберите подходящий тарифный план:"
    
    # Создаем клавиатуру с тарифами
    builder = InlineKeyboardBuilder()
    
    for plan in tariffs:
        builder.add(InlineKeyboardButton(
            text=f"{plan.name} - {plan.price}₽",
            callback_data=f"plan:{plan.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="◀️ Назад к каналам",
        callback_data="back_to_channels"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        plans_text, 
        reply_markup=builder.as_markup(), 
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_channels")
async def back_to_channels_list(callback: CallbackQuery):
    """Возврат к списку каналов"""
    # Получаем активные каналы
    channels = await ChannelDAL.get_active_channels()
    
    text = "📺 <b>Выберите канал для подписки:</b>\n\n"
    
    # Создаем клавиатуру с каналами
    builder = InlineKeyboardBuilder()
    
    for channel in channels:
        builder.add(InlineKeyboardButton(
            text=channel.name,
            callback_data=f"select_channel:{channel.id}"
        ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"))
async def process_plan_selection(callback: CallbackQuery, state: FSMContext):
    plan_id = int(callback.data.split(":")[1])

    plan = await TariffDAL.get_by_id(plan_id)

    if not plan:
        await callback.answer("Тарифный план не найден", show_alert=True)
        return

    # Получаем канал, к которому привязан тариф
    channel = await ChannelDAL.get_by_id(plan.channel_id)
    if not channel:
        await callback.answer("Ошибка: канал для тарифа не найден", show_alert=True)
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
        elif method.code == "stars" and config.payment.stars_enabled:
            enabled_methods.append(method)

    if not enabled_methods:
        await callback.answer("В данный момент оплата недоступна. Попробуйте позже.", show_alert=True)
        return

    await state.set_state(PaymentStates.waiting_for_payment_method)
    await state.update_data(selected_plan_id=plan_id)

    if len(enabled_methods) > 1:
        methods_text = (
            f"Вы выбрали тариф: <b>{plan.name}</b> для канала <b>{channel.name}</b>\n\n"
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

    # Получаем канал, к которому привязан тариф
    channel = await ChannelDAL.get_by_id(plan.channel_id)
    if not channel:
        await callback.answer("Ошибка: канал для тарифа не найден", show_alert=True)
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
        await process_manual_payment(callback, state, plan, channel, payment_method, default_currency, final_price)
    elif method_code == "youkassa":
        await yookassa_payment_route(callback, plan, default_currency, final_price)
    elif method_code == "tinkoff":
        await tinkoff_payment_route(callback, plan, default_currency, final_price)
    elif method_code == "cryptobot":
        await cryptobot_payment_route(callback, plan, default_currency, final_price)
    elif method_code == "stars":
        await process_stars_payment(callback, state)

    await callback.answer()


async def process_manual_payment(
    callback: CallbackQuery, 
    state: FSMContext, 
    plan: TariffPlan, 
    channel: Channel, 
    payment_method, 
    currency, 
    final_price
):
    await state.set_state(PaymentStates.waiting_for_payment_screenshot)

    payment_text = (
        f"Вы выбрали тариф: <b>{plan.name}</b> для канала <b>{channel.name}</b>\n\n"
        f"Сумма к оплате: <b>{final_price} {currency.symbol}</b>\n\n"
        f"Для оплаты переведите указанную сумму на следующие реквизиты:\n"
        f"💳 <b>Номер карты:</b> <code>{config.payment.manual_card_number}</code>\n"
        f"👤 <b>Получатель:</b> {config.payment.manual_recipient_name}\n\n"
        f"После оплаты, отправьте скриншот или фото чека об оплате.\n"
        f"Ваша заявка будет обработана администратором."
    )

    await callback.message.edit_text(
        payment_text, reply_markup=SubscriptionKeyboard.back_to_tariffs(channel.id), parse_mode="HTML"
    )

@router.callback_query(F.data.startswith('back_to_tariffs:'))
async def handle_back_to_tariffs(call: CallbackQuery):
    channel_id = call.data.split(':')[1]
    await show_channel_tariffs(call, c_id=channel_id)

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment_process(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get("payment_id")

    if payment_id:
        await PaymentDAL.cancel_payment(payment_id)

    await state.clear()

    await back_to_channels_list(callback)


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

    # Получаем канал, к которому привязан тариф
    channel = await ChannelDAL.get_by_id(plan.channel_id)
    if not channel:
        await message.answer("Ошибка: канал для тарифа не найден")
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

    try:
        await message.bot.send_photo(
            chat_id=config.payment.manual_channel_id,
            photo=file_id,
            caption=(
                f"🔔 <b>Новая заявка на оплату</b>\n\n"
                f"👤 Пользователь: {message.from_user.full_name} (@{message.from_user.username})\n"
                f"💰 Сумма: {final_price} {currency.symbol}\n"
                f"📋 Тариф: {plan.name}\n"
                f"📺 Канал: {channel.name}\n"
                f"💳 Способ оплаты: {payment_method.name}\n"
                f"🆔 ID платежа: {payment.id}"
            ),
            reply_markup=AdminKeyboard.payment_approval(payment.id),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору {config.payment.manual_channel_id}: {e}")


@router.message(F.text.in_(["📺 Подписка", "📺 Подписки"]))
async def show_subscriptions(message: Message):
    user = await UserDAL.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}",
    )

    # Получаем активную подписку пользователя
    subscription_data = await SubscriptionDAL.get_by_telegram_id(message.from_user.id)
    
    if subscription_data:
        subscription, plan, _ = subscription_data
        
        # Получаем канал, к которому дает доступ тариф
        channel = await ChannelDAL.get_by_id(plan.channel_id)
        
        if channel:
            # Проверяем, подписан ли пользователь на канал в Telegram
            is_subscribed = await check_user_channel_subscription(
                message.bot, 
                message.from_user.id, 
                channel.channel_id
            )
            
            subscription_text = f"📺 <b>Ваша подписка</b>\n\n"
            subscription_text += f"Тариф: <b>{plan.name}</b>\n"
            subscription_text += f"Срок действия: до <b>{subscription.end_date.strftime('%d.%m.%Y')}</b>\n\n"
            
            subscription_text += f"📺 <b>Доступный канал:</b>\n"
            
            if is_subscribed:
                subscription_text += f"\n✅ <b>Вы уже подписаны на канал:</b>\n"
                subscription_text += f"- {channel.name}\n"
            else:
                subscription_text += f"\n❗️ <b>Необходимо подписаться:</b>\n"
                subscription_text += f"- {channel.name}\n"
            
            await message.answer(subscription_text, parse_mode="HTML")
            
            if not is_subscribed:
                builder = InlineKeyboardBuilder()
                builder.add(InlineKeyboardButton(
                    text=f"Подписаться на {channel.name}", 
                    url=channel.invite_link
                ))
                builder.add(InlineKeyboardButton(
                    text="🔄 Обновить статус подписки", 
                    callback_data="update_channel_subscription"
                ))
                
                builder.adjust(1)
                
                await message.answer(
                    "Для получения полного доступа, пожалуйста, подпишитесь на канал:",
                    reply_markup=builder.as_markup()
                )
        else:
            await message.answer(
                "⚠️ Ошибка: канал для вашего тарифа не найден. Обратитесь к администратору.",
                parse_mode="HTML"
            )
    else:
        subscription_text = (
            f"📺 <b>У вас нет активных подписок</b>\n\n"
            f"Нажмите на кнопку '💼 Тарифы', чтобы выбрать канал и подходящий тариф"
        )
        
        await message.answer(subscription_text, parse_mode="HTML")


@router.callback_query(F.data == "update_channel_subscription")
async def update_channel_subscription(callback: CallbackQuery):
    """Обновляет статус подписки на канал"""
    subscription_data = await SubscriptionDAL.get_by_telegram_id(callback.from_user.id)
    
    if not subscription_data:
        await callback.message.edit_text("У вас нет активных подписок.")
        await callback.answer()
        return
    
    subscription, plan, _ = subscription_data
    
    # Получаем канал, к которому дает доступ тариф
    channel = await ChannelDAL.get_by_id(plan.channel_id)
    
    if not channel:
        await callback.message.edit_text("Ошибка: канал для вашего тарифа не найден.")
        await callback.answer()
        return
    
    # Проверяем, подписан ли пользователь на канал в Telegram
    is_subscribed = await check_user_channel_subscription(
        callback.bot, 
        callback.from_user.id, 
        channel.channel_id
    )
    
    if is_subscribed:
        await callback.message.edit_text(f"✅ Отлично! Вы подписаны на канал {channel.name}.")
    else:
        text = f"Для получения доступа, пожалуйста, подпишитесь на канал {channel.name}:"
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text=f"Подписаться на {channel.name}", 
            url=channel.invite_link
        ))
        builder.add(InlineKeyboardButton(
            text="🔄 Обновить статус подписки", 
            callback_data="update_channel_subscription"
        ))
        
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    
    await callback.answer()


@router.message(F.text == "ℹ️ Информация")
async def show_info(message: Message):
    info_text = (
        "ℹ️ <b>О боте</b>\n\n"
        "Этот бот позволяет оформить подписку на наши каналы.\n\n"
        "📋 <b>Доступные команды:</b>\n"
        "/start - Запустить бота\n"
        "💼 Тарифы - Просмотр доступных каналов и тарифов\n"
        "📺 Подписки - Информация о ваших подписках\n\n"
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
    if config.payment.stars_enabled:
        available_methods.append("⭐ Telegram Stars")

    if available_methods:
        info_text += "<b>Доступные способы оплаты:</b>\n"
        for method in available_methods:
            info_text += f"- {method}\n"

    await message.answer(info_text, parse_mode="HTML")