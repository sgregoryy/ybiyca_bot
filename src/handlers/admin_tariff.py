from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from src.utils.states import AdminStates
from src.keyboards.inline import AdminKeyboard
from src.db.DALS.tariff import TariffDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.payment import PaymentDAL
from src.config import config
import logging

router = Router()
logger = logging.getLogger(__name__)

# Обработчик добавления нового тарифа
@router.callback_query(F.data == "tariff:add")
async def add_tariff_start(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_tariff_name)
    await callback.message.answer("Введите название нового тарифа (например, '1 месяц'):")
    await callback.answer()

@router.message(AdminStates.waiting_for_tariff_name)
async def process_tariff_name(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config.telegram.admin_ids:
        return
    
    tariff_name = message.text.strip()
    if not tariff_name:
        await message.answer("Название тарифа не может быть пустым. Пожалуйста, введите название:")
        return
    
    # Сохраняем название тарифа
    await state.update_data(tariff_name=tariff_name)
    
    # Генерируем код тарифа (slug) на основе названия
    tariff_code = tariff_name.lower().replace(' ', '_')
    await state.update_data(tariff_code=tariff_code)
    
    # Переходим к вводу цены
    await state.set_state(AdminStates.waiting_for_tariff_price)
    await message.answer(f"Введите цену тарифа '{tariff_name}' в рублях (только число):")

@router.message(AdminStates.waiting_for_tariff_price)
async def process_tariff_price(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config.telegram.admin_ids:
        return
    
    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError("Цена должна быть положительным числом")
    except ValueError:
        await message.answer("Пожалуйста, введите корректную цену (только положительное число):")
        return
    
    # Сохраняем цену
    await state.update_data(tariff_price=price)
    
    # Переходим к вводу длительности
    await state.set_state(AdminStates.waiting_for_tariff_duration)
    await message.answer("Введите длительность тарифа в днях (только число):")

@router.message(AdminStates.waiting_for_tariff_duration)
async def process_tariff_duration(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config.telegram.admin_ids:
        return
    
    try:
        duration = int(message.text.strip())
        if duration <= 0:
            raise ValueError("Длительность должна быть положительным числом")
    except ValueError:
        await message.answer("Пожалуйста, введите корректную длительность (только положительное число):")
        return
    
    # Получаем все данные из состояния
    data = await state.get_data()
    tariff_name = data.get("tariff_name")
    tariff_code = data.get("tariff_code")
    tariff_price = data.get("tariff_price")
    
    # Сбрасываем состояние
    await state.clear()
    
    # Проверяем, существует ли тариф с таким кодом
    existing_tariff = await TariffDAL.get_by_code(tariff_code)
    
    if existing_tariff:
        await message.answer(f"Тариф с кодом '{tariff_code}' уже существует. Пожалуйста, используйте другое название.")
        return
    
    # Создаем новый тариф
    new_tariff = await TariffDAL.create_tariff(
        name=tariff_name,
        code=tariff_code,
        price=tariff_price,
        duration_days=duration
    )
    
    await message.answer(
        f"✅ Тариф успешно добавлен:\n\n"
        f"📋 Название: {tariff_name}\n"
        f"💰 Цена: {tariff_price}₽\n"
        f"⏱ Длительность: {duration} дней\n"
        f"🔄 Активен: ✅"
    )
    
    # Показываем админ-меню с тарифами
    await message.answer(
        "📝 Управление тарифами",
        reply_markup=AdminKeyboard.manage_tariffs_menu()
    )

@router.callback_query(F.data == "tariff:list_edit")
async def list_tariffs_for_edit(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    # Получаем все тарифы
    tariffs = await TariffDAL.get_all_plans()
    
    if not tariffs:
        await callback.message.edit_text(
            "📋 Тарифы не найдены. Сначала добавьте тарифы.",
            reply_markup=AdminKeyboard.manage_tariffs_menu()
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру для выбора тарифа
    builder = InlineKeyboardBuilder()
    for tariff in tariffs:
        builder.add(InlineKeyboardButton(
            text=f"{tariff.name} - {tariff.price}₽",
            callback_data=f"tariff:edit:{tariff.id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="admin:manage_tariffs"
    ))
    
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📝 Выберите тариф для редактирования:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("tariff:edit:"))
async def edit_tariff(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    tariff_id = int(callback.data.split(":")[2])
    
    # Получаем тариф по ID
    tariff = await TariffDAL.get_by_id(tariff_id)
    
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return
    
    # Сохраняем ID тарифа в состояние
    await state.set_state(AdminStates.waiting_for_tariff_field)
    await state.update_data(tariff_id=tariff_id)
    
    # Создаем клавиатуру для выбора поля для редактирования
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Название", callback_data="tariff:field:name"),
        InlineKeyboardButton(text="Цена", callback_data="tariff:field:price"),
        InlineKeyboardButton(text="Длительность", callback_data="tariff:field:duration"),
        InlineKeyboardButton(text=f"Активность: {'Вкл ✅' if tariff.is_active else 'Выкл ❌'}", 
                           callback_data="tariff:field:active"),
        InlineKeyboardButton(text="Удалить тариф", callback_data="tariff:delete"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="tariff:list_edit")
    )
    builder.adjust(1)
    
    tariff_info = (
        f"📝 <b>Редактирование тарифа</b>\n\n"
        f"📋 Название: {tariff.name}\n"
        f"💰 Цена: {tariff.price}₽\n"
        f"⏱ Длительность: {tariff.duration_days} дней\n"
        f"🔄 Активен: {'✅' if tariff.is_active else '❌'}\n"
        f"🔢 Порядок: {tariff.display_order}\n\n"
        f"Выберите поле для редактирования:"
    )
    
    await callback.message.edit_text(
        tariff_info,
        reply_markup=builder.as_markup(), parse_mode='HTML'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("tariff:field:"))
async def edit_tariff_field(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    field = callback.data.split(":")[2]
    
    # Если выбрано поле активности, просто переключаем его
    if field == "active":
        data = await state.get_data()
        tariff_id = data.get("tariff_id")
        
        # Переключаем активность тарифа
        tariff = await TariffDAL.toggle_active(tariff_id)
        
        if not tariff:
            await callback.answer("Тариф не найден", show_alert=True)
            return
        
        await callback.answer(
            f"Тариф {'активирован' if tariff.is_active else 'деактивирован'}",
            show_alert=True
        )
        
        # Возвращаемся к редактированию тарифа
        await edit_tariff(callback, state)
        return
    
    # Для других полей запрашиваем новое значение
    await state.update_data(field=field)
    await state.set_state(AdminStates.waiting_for_tariff_new_value)
    
    field_names = {
        "name": "название",
        "price": "цену",
        "duration": "длительность (в днях)"
    }
    
    await callback.message.answer(f"Введите новое {field_names.get(field, 'значение')}:")
    await callback.answer()

@router.message(AdminStates.waiting_for_tariff_new_value)
async def process_tariff_new_value(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config.telegram.admin_ids:
        return
    
    data = await state.get_data()
    tariff_id = data.get("tariff_id")
    field = data.get("field")
    
    # Получаем тариф
    tariff = await TariffDAL.get_by_id(tariff_id)
    
    if not tariff:
        await message.answer("Тариф не найден")
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
            
        elif field == "price":
            new_value = int(message.text.strip())
            if new_value <= 0:
                await message.answer("Цена должна быть положительным числом")
                return
            update_data["price"] = new_value
            
        elif field == "duration":
            new_value = int(message.text.strip())
            if new_value <= 0:
                await message.answer("Длительность должна быть положительным числом")
                return
            update_data["duration_days"] = new_value
            
        # Обновляем тариф
        updated_tariff = await TariffDAL.update(tariff_id, **update_data)
        
        if not updated_tariff:
            await message.answer("Ошибка при обновлении тарифа")
            return
            
    except ValueError:
        await message.answer("Пожалуйста, введите корректное значение")
        return
    
    # Сбрасываем состояние
    await state.clear()
    
    await message.answer(f"✅ Тариф успешно обновлен")
    
    # Возвращаем меню управления тарифами
    await message.answer(
        "📝 Управление тарифами",
        reply_markup=AdminKeyboard.manage_tariffs_menu()
    )

@router.callback_query(F.data == "tariff:delete")
async def delete_tariff(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    data = await state.get_data()
    tariff_id = data.get("tariff_id")
    
    # Получаем тариф
    tariff = await TariffDAL.get_by_id(tariff_id)
    
    if not tariff:
        await callback.answer("Тариф не найден", show_alert=True)
        return
    
    # Проверяем, есть ли активные подписки на этот тариф
    subs_data = await SubscriptionDAL.get_plan_statistics()
    has_active_subscriptions = tariff.name in subs_data and subs_data[tariff.name] > 0
    
    if has_active_subscriptions:
        await callback.answer(
            "Невозможно удалить тариф, так как существуют активные подписки на него. "
            "Деактивируйте тариф вместо удаления.", 
            show_alert=True
        )
        return
    
    await TariffDAL.toggle_active(tariff_id)
    
    await callback.answer(
        "Тариф был деактивирован вместо удаления, чтобы сохранить историю платежей.",
        show_alert=True
    )
    
    # Сбрасываем состояние
    await state.clear()
    
    # Возвращаемся к списку тарифов
    await callback.message.edit_text(
        "📝 Управление тарифами",
        reply_markup=AdminKeyboard.manage_tariffs_menu()
    )