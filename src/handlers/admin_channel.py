from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from src.db.DALS.subscription import SubscriptionDAL
from src.utils.states import AdminStates
from src.keyboards.inline import AdminKeyboard
from src.db.DALS.channel import ChannelDAL
from src.db.DALS.tariff import TariffDAL
from src.config import config
import logging

router = Router()
logger = logging.getLogger(__name__)

# Обработчик для входа в меню управления каналами
@router.callback_query(F.data == "admin:manage_channels")
async def manage_channels(callback: CallbackQuery):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    # Получаем все каналы с привязанными тарифами
    channels_with_plans = await ChannelDAL.get_channels_with_plans()
    
    channels_text = f"📝 <b>Управление каналами доступа</b>\n\n"
    
    if not channels_with_plans:
        channels_text += "Каналы не найдены. Добавьте первый канал."
    else:
        for i, (channel, plans) in enumerate(channels_with_plans, 1):
            # Формируем список тарифов для канала
            plan_names = [plan.name for plan in plans]
            plans_text = ", ".join(plan_names) if plan_names else "Нет тарифов"
            
            channels_text += (
                f"{i}. <b>{channel.name}</b>\n"
                f"   ID: {channel.channel_id}\n"
                f"   Активен: {'✅' if channel.is_active else '❌'}\n"
                f"   Тарифы: {plans_text}\n\n"
            )
    
    await callback.message.edit_text(
        channels_text,
        reply_markup=AdminKeyboard.manage_channels_menu()
    )
    await callback.answer()

# Обработчик добавления нового канала
@router.callback_query(F.data == "channel:add")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_channel_name)
    await callback.message.answer("Введите название нового канала:")
    await callback.answer()

@router.message(AdminStates.waiting_for_channel_name)
async def process_channel_name(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config.telegram.admin_ids:
        return
    
    channel_name = message.text.strip()
    if not channel_name:
        await message.answer("Название канала не может быть пустым. Пожалуйста, введите название:")
        return
    
    # Сохраняем название канала
    await state.update_data(channel_name=channel_name)
    
    # Переходим к вводу ID канала
    await state.set_state(AdminStates.waiting_for_channel_id)
    await message.answer(
        f"Введите ID канала для '{channel_name}' (должно быть целое число, например: -1001234567890):"
    )

@router.message(AdminStates.waiting_for_channel_id)
async def process_channel_id(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config.telegram.admin_ids:
        return
    
    try:
        channel_id = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID канала (должно быть целое число):")
        return
    
    # Проверяем, существует ли канал с таким ID
    existing_channel = await ChannelDAL.get_by_telegram_id(channel_id)
    if existing_channel:
        await message.answer(f"Канал с ID {channel_id} уже существует. Пожалуйста, введите другой ID:")
        return
    
    # Сохраняем ID канала
    await state.update_data(channel_id=channel_id)
    
    # Переходим к вводу ссылки-приглашения
    await state.set_state(AdminStates.waiting_for_channel_link)
    await message.answer(
        "Введите ссылку-приглашение для канала (должна начинаться с https://t.me/ или t.me/):"
    )

@router.message(AdminStates.waiting_for_channel_link)
async def process_channel_link(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config.telegram.admin_ids:
        return
    
    channel_link = message.text.strip()
    if not channel_link.startswith(("https://t.me/", "t.me/")):
        await message.answer(
            "Ссылка должна начинаться с https://t.me/ или t.me/. Пожалуйста, введите корректную ссылку:"
        )
        return
    
    # Сохраняем ссылку-приглашение
    await state.update_data(channel_link=channel_link)
    
    # Получаем все данные из состояния
    data = await state.get_data()
    channel_name = data.get("channel_name")
    channel_id = data.get("channel_id")
    
    # Создаем новый канал
    channel = await ChannelDAL.create_channel(
        name=channel_name,
        channel_id=channel_id,
        invite_link=channel_link
    )
    
    # Получаем все тарифные планы для выбора
    tariff_plans = await TariffDAL.get_all_plans()
    
    # Сбрасываем состояние
    await state.clear()
    
    await message.answer(
        f"✅ Канал успешно добавлен:\n\n"
        f"📋 Название: {channel_name}\n"
        f"🆔 ID: {channel_id}\n"
        f"🔗 Ссылка: {channel_link}\n\n"
        f"Теперь вы можете выбрать тарифные планы, которые будут иметь доступ к этому каналу:"
    )
    
    # Создаем клавиатуру для выбора тарифных планов
    builder = InlineKeyboardBuilder()
    for plan in tariff_plans:
        builder.add(InlineKeyboardButton(
            text=f"{plan.name} ({plan.price}₽)",
            callback_data=f"channel:add_plan:{channel.id}:{plan.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="◀️ Назад к управлению каналами",
        callback_data="admin:manage_channels"
    ))
    
    builder.adjust(1)
    
    await message.answer(
        "Выберите тарифные планы для канала:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("channel:add_plan:"))
async def add_plan_to_channel(callback: CallbackQuery):
    # Все проверки на администратора уже сделаны через AdminFilter
    
    parts = callback.data.split(":")
    channel_id = int(parts[2])
    plan_id = int(parts[3])
    
    # Получаем информацию о канале и плане
    channel = await ChannelDAL.get_by_id(channel_id)
    plan = await TariffDAL.get_by_id(plan_id)
    
    if not channel or not plan:
        await callback.answer("Канал или тарифный план не найден", show_alert=True)
        return
    
    # Обновляем тарифный план, устанавливая привязку к каналу
    updated_plan = await TariffDAL.update(plan_id, channel_id=channel_id)
    
    if not updated_plan:
        await callback.answer("Не удалось привязать тариф к каналу", show_alert=True)
        return
    
    await callback.answer(f"Тариф {plan.name} добавлен к каналу {channel.name}", show_alert=True)
    
    # Обновляем список тарифных планов в сообщении
    plans = await TariffDAL.get_tariffs_by_channel(channel_id)
    plan_names = [p.name for p in plans]
    plans_text = ", ".join(plan_names) if plan_names else "Нет тарифов"
    
    text = (
        f"✅ Канал успешно обновлен:\n\n"
        f"📋 Название: {channel.name}\n"
        f"🆔 ID: {channel.channel_id}\n"
        f"🔗 Ссылка: {channel.invite_link}\n"
        f"📊 Тарифы: {plans_text}\n\n"
        f"Выберите еще тарифные планы или вернитесь к управлению каналами:"
    )
    
    # Получаем все тарифные планы для выбора
    all_plans = await TariffDAL.get_all_plans()
    
    # Создаем клавиатуру для выбора тарифных планов
    builder = InlineKeyboardBuilder()
    for p in all_plans:
        # Проверяем, добавлен ли уже этот план
        is_added = p.channel_id == channel_id
        prefix = "✅ " if is_added else ""
        
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{p.name} ({p.price}₽)",
            callback_data=f"channel:{'remove_plan' if is_added else 'add_plan'}:{channel.id}:{p.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="◀️ Назад к управлению каналами",
        callback_data="admin:manage_channels"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("channel:remove_plan:"))
async def remove_plan_from_channel(callback: CallbackQuery):
    # Все проверки на администратора уже сделаны через AdminFilter
    
    parts = callback.data.split(":")
    channel_id = int(parts[2])
    plan_id = int(parts[3])
    
    # Получаем информацию о канале и плане
    channel = await ChannelDAL.get_by_id(channel_id)
    plan = await TariffDAL.get_by_id(plan_id)
    
    if not channel or not plan:
        await callback.answer("Канал или тарифный план не найден", show_alert=True)
        return
    
    # Проверяем, есть ли активные подписки на этот тариф
    plan_stats = await SubscriptionDAL.get_plan_statistics()
    has_active_subscriptions = plan.name in plan_stats and plan_stats[plan.name] > 0
    
    if has_active_subscriptions:
        await callback.answer(
            "Невозможно отвязать тариф от канала, так как существуют активные подписки на него.",
            show_alert=True
        )
        return
    
    # Отвязываем тарифный план от канала (устанавливаем channel_id в NULL или в ID другого канала)
    # В вашей схеме лучше деактивировать тариф или переназначить ему другой канал
    updated_plan = await TariffDAL.update(plan_id, is_active=False)
    
    if not updated_plan:
        await callback.answer("Не удалось отвязать тариф от канала", show_alert=True)
        return
    
    await callback.answer(f"Тариф {plan.name} отвязан от канала {channel.name}", show_alert=True)
    
    # Обновляем список тарифных планов в сообщении
    plans = await TariffDAL.get_tariffs_by_channel(channel_id)
    plan_names = [p.name for p in plans]
    plans_text = ", ".join(plan_names) if plan_names else "Нет тарифов"
    
    text = (
        f"✅ Канал успешно обновлен:\n\n"
        f"📋 Название: {channel.name}\n"
        f"🆔 ID: {channel.channel_id}\n"
        f"🔗 Ссылка: {channel.invite_link}\n"
        f"📊 Тарифы: {plans_text}\n\n"
        f"Выберите тарифные планы или вернитесь к управлению каналами:"
    )
    
    # Получаем все тарифные планы для выбора
    all_plans = await TariffDAL.get_all_plans()
    
    # Создаем клавиатуру для выбора тарифных планов
    builder = InlineKeyboardBuilder()
    for p in all_plans:
        # Проверяем, добавлен ли уже этот план
        is_added = p.channel_id == channel_id and p.is_active
        prefix = "✅ " if is_added else ""
        
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{p.name} ({p.price}₽)",
            callback_data=f"channel:{'remove_plan' if is_added else 'add_plan'}:{channel.id}:{p.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="◀️ Назад к управлению каналами",
        callback_data="admin:manage_channels"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

# Обработчик для редактирования каналов
@router.callback_query(F.data == "channel:list_edit")
async def list_channels_for_edit(callback: CallbackQuery):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    # Получаем все каналы
    channels = await ChannelDAL.get_all_channels()
    
    if not channels:
        await callback.message.edit_text(
            "📋 Каналы не найдены. Сначала добавьте каналы.",
            reply_markup=AdminKeyboard.manage_channels_menu()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для выбора канала
    builder = InlineKeyboardBuilder()
    for channel in channels:
        status = "✅" if channel.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {channel.name}",
            callback_data=f"channel:edit:{channel.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="admin:manage_channels"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📝 Выберите канал для редактирования:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("channel:edit:"))
async def edit_channel(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    channel_id = int(callback.data.split(":")[2])
    
    # Получаем информацию о канале
    channel = await ChannelDAL.get_by_id(channel_id)
    
    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return
    
    # Получаем тарифные планы для канала
    plans = await ChannelDAL.get_plans_for_channel(channel_id)
    plan_names = [plan.name for plan in plans]
    plans_text = ", ".join(plan_names) if plan_names else "Нет тарифов"
    
    # Сохраняем ID канала в состояние
    await state.set_state(AdminStates.waiting_for_channel_field)
    await state.update_data(channel_id=channel_id)
    
    # Создаем клавиатуру для выбора поля для редактирования
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Название", callback_data="channel:field:name"),
        InlineKeyboardButton(text="Ссылка", callback_data="channel:field:link"),
        InlineKeyboardButton(text=f"Активность: {'Вкл ✅' if channel.is_active else 'Выкл ❌'}", 
                           callback_data="channel:field:active"),
        InlineKeyboardButton(text="Тарифные планы", callback_data=f"channel:edit_plans:{channel_id}"),
        InlineKeyboardButton(text="Удалить канал", callback_data="channel:delete"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="channel:list_edit")
    )
    builder.adjust(1)
    
    channel_info = (
        f"📝 <b>Редактирование канала</b>\n\n"
        f"📋 Название: {channel.name}\n"
        f"🆔 ID: {channel.channel_id}\n"
        f"🔗 Ссылка: {channel.invite_link}\n"
        f"🔄 Активен: {'✅' if channel.is_active else '❌'}\n"
        f"📊 Тарифы: {plans_text}\n\n"
        f"Выберите поле для редактирования:"
    )
    
    await callback.message.edit_text(
        channel_info,
        reply_markup=builder.as_markup(), parse_mode='HTML'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("channel:field:"))
async def edit_channel_field(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    field = callback.data.split(":")[2]
    
    # Если выбрано поле активности, просто переключаем его
    if field == "active":
        data = await state.get_data()
        channel_id = data.get("channel_id")
        
        # Переключаем активность канала
        channel = await ChannelDAL.toggle_active(channel_id)
        
        if not channel:
            await callback.answer("Канал не найден", show_alert=True)
            return
        
        await callback.answer(
            f"Канал {'активирован' if channel.is_active else 'деактивирован'}",
            show_alert=True
        )
        
        # Возвращаемся к редактированию канала
        await edit_channel(callback, state)
        return
    
    # Для других полей запрашиваем новое значение
    await state.update_data(field=field)
    await state.set_state(AdminStates.waiting_for_channel_new_value)
    
    field_names = {
        "name": "название",
        "link": "ссылку-приглашение"
    }
    
    await callback.message.answer(f"Введите новое {field_names.get(field, 'значение')}:")
    await callback.answer()

@router.message(AdminStates.waiting_for_channel_new_value)
async def process_channel_new_value(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config.telegram.admin_ids:
        return
    
    data = await state.get_data()
    channel_id = data.get("channel_id")
    field = data.get("field")
    
    # Получаем канал
    channel = await ChannelDAL.get_by_id(channel_id)
    
    if not channel:
        await message.answer("Канал не найден")
        await state.clear()
        return
    
    # Обновляем поле в зависимости от типа
    try:
        update_data = {}
        
        if field == "name":
            new_value = message.text.strip()
            if not new_value:
                await message.answer("Название не может быть пустым")
                return
            update_data["name"] = new_value
            
        elif field == "link":
            new_value = message.text.strip()
            if not new_value.startswith(("https://t.me/", "t.me/")):
                await message.answer("Ссылка должна начинаться с https://t.me/ или t.me/")
                return
            update_data["invite_link"] = new_value
            
        # Обновляем канал
        updated_channel = await ChannelDAL.update_channel(channel_id, **update_data)
        
        if not updated_channel:
            await message.answer("Ошибка при обновлении канала")
            return
            
    except ValueError:
        await message.answer("Пожалуйста, введите корректное значение")
        return
    
    # Сбрасываем состояние
    await state.clear()
    
    await message.answer(f"✅ Канал успешно обновлен")
    
    # Возвращаем меню управления каналами
    channels = await ChannelDAL.get_all_channels()
    
    # Создаем клавиатуру для выбора канала
    builder = InlineKeyboardBuilder()
    for ch in channels:
        status = "✅" if ch.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {ch.name}",
            callback_data=f"channel:edit:{ch.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="admin:manage_channels"
    ))
    
    builder.adjust(1)
    
    await message.answer(
        "📝 Выберите канал для редактирования или вернитесь к управлению каналами:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("channel:edit_plans:"))
async def edit_channel_plans(callback: CallbackQuery):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    channel_id = int(callback.data.split(":")[2])
    
    # Получаем информацию о канале
    channel = await ChannelDAL.get_by_id(channel_id)
    
    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return
    
    # Получаем тарифные планы для канала
    plans = await ChannelDAL.get_plans_for_channel(channel_id)
    
    # Получаем все тарифные планы
    all_plans = await TariffDAL.get_all_plans()
    
    # Создаем клавиатуру для выбора тарифных планов
    builder = InlineKeyboardBuilder()
    for p in all_plans:
        # Проверяем, добавлен ли уже этот план
        is_added = any(existing_plan.id == p.id for existing_plan in plans)
        prefix = "✅ " if is_added else ""
        
        builder.add(InlineKeyboardButton(
            text=f"{prefix}{p.name} ({p.price}₽)",
            callback_data=f"channel:{'remove_plan' if is_added else 'add_plan'}:{channel.id}:{p.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="◀️ Назад к редактированию канала",
        callback_data=f"channel:edit:{channel_id}"
    ))
    
    builder.adjust(1)
    
    plan_names = [p.name for p in plans]
    plans_text = ", ".join(plan_names) if plan_names else "Нет тарифов"
    
    text = (
        f"📝 <b>Управление тарифами для канала:</b> {channel.name}\n\n"
        f"Текущие тарифы: {plans_text}\n\n"
        f"Выберите тарифы для добавления или удаления:"
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "channel:delete")
async def delete_channel(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    data = await state.get_data()
    channel_id = data.get("channel_id")
    
    # Получаем канал
    channel = await ChannelDAL.get_by_id(channel_id)
    
    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return
    
    # Удаляем канал
    await ChannelDAL.delete_channel(channel_id)
    
    await callback.answer(f"Канал {channel.name} успешно удален", show_alert=True)
    
    # Сбрасываем состояние
    await state.clear()
    
    # Возвращаемся к списку каналов
    await callback.message.edit_text(
        "📝 Управление каналами",
        reply_markup=AdminKeyboard.manage_channels_menu()
    )