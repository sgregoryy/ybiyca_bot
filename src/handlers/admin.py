from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from src.filters.admin import AdminFilter
from src.keyboards.inline import AdminKeyboard
from src.utils.states import AdminStates
from src.db.DALS.user import UserDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.tariff import TariffDAL
from src.db.DALS.payment import PaymentDAL
from src.config import config
import datetime
import logging
import asyncio

router = Router()
logger = logging.getLogger(__name__)

# Функционал рассылки сообщений
async def broadcast_message(bot, text, disable_notification=False):
    """
    Отправляет сообщение всем активным пользователям
    """
    # Получаем всех активных пользователей
    users = await UserDAL.get_active_users()
    
    success_count = 0
    for user in users:
        try:
            await bot.send_message(
                chat_id=user.user_id,
                text=text,
                disable_notification=disable_notification
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Избегаем ограничений по флуду
        except Exception as e:
            if "Forbidden" in str(e):
                logger.error(f"Пользователь {user.user_id} заблокировал бота")
                await UserDAL.mark_inactive(user.user_id)
            elif "retry after" in str(e).lower():
                retry_time = int(''.join(filter(str.isdigit, str(e))))
                logger.error(f"Превышен лимит запросов для {user.user_id}. Ожидание {retry_time} секунд.")
                await asyncio.sleep(retry_time)
                try:
                    await bot.send_message(
                        chat_id=user.user_id,
                        text=text,
                        disable_notification=disable_notification
                    )
                    success_count += 1
                except Exception as inner_e:
                    logger.error(f"Не удалось отправить сообщение пользователю {user.user_id} после ожидания: {inner_e}")
            else:
                logger.error(f"Не удалось отправить сообщение пользователю {user.user_id}: {e}")
    
    return success_count

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id in config.telegram.admin_ids:
        await message.answer("👑 Панель администратора", reply_markup=AdminKeyboard.admin_menu())

@router.callback_query(F.data == "admin:statistics")
async def show_statistics(callback: CallbackQuery):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    # Получаем общее количество пользователей
    total_users = len(await UserDAL.get_all())
    
    # Получаем активных пользователей (с подпиской)
    active_users = await SubscriptionDAL.count_active()
    
    # Получаем новых пользователей за сегодня
    new_users_today = len(await UserDAL.get_new_users_today())
    
    # Получаем ожидающие платежи
    pending_payments = await PaymentDAL.count_pending()
    
    # Получаем статистику доходов
    approved_payments = await PaymentDAL.get_revenue_stats()
    total_revenue = approved_payments["total_revenue"]
    
    # Получаем подписки по тарифам
    plan_stats = await SubscriptionDAL.get_plan_statistics()
    
    stats_text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Активных подписок: {active_users}\n"
        f"🆕 Новых пользователей сегодня: {new_users_today}\n"
        f"⏳ Ожидающих проверки платежей: {pending_payments}\n"
        f"💰 Общий доход: {total_revenue}₽\n\n"
        f"📋 <b>Подписки по тарифам:</b>\n"
    )
    
    for plan_name, count in plan_stats.items():
        stats_text += f"- {plan_name}: {count}\n"
    
    await callback.message.edit_text(stats_text, reply_markup=AdminKeyboard.admin_menu())
    await callback.answer()

@router.callback_query(F.data == "admin:broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.message.answer(
        "📨 Отправьте сообщение, которое хотите разослать всем пользователям"
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in config.telegram.admin_ids:
        return
    
    broadcast_text = message.text or message.caption
    
    if not broadcast_text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение для рассылки")
        return
    
    await state.clear()
    
    await message.answer("📨 Начинаем рассылку сообщений...")
    
    success_count = await broadcast_message(message.bot, broadcast_text)
    
    await message.answer(f"✅ Рассылка завершена. Сообщение доставлено {success_count} пользователям.")

@router.callback_query(F.data == "admin:payments")
async def show_pending_payments(callback: CallbackQuery):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    # Получаем ожидающие платежи
    pending_payments = await PaymentDAL.get_pending_payments()
    
    if not pending_payments:
        await callback.message.edit_text(
            "📌 Нет ожидающих проверки платежей",
            reply_markup=AdminKeyboard.admin_menu()
        )
        await callback.answer()
        return
    
    payments_text = f"💰 <b>Ожидающие проверки платежи ({len(pending_payments)}):</b>\n\n"
    
    for i, row in enumerate(pending_payments[:5], 1):
        payment, user, plan = row
        
        payments_text += (
            f"{i}. ID: {payment.id}\n"
            f"👤 Пользователь: {user.full_name} (@{user.username})\n"
            f"💰 Сумма: {payment.amount}₽\n"
            f"📋 Тариф: {plan.name}\n"
            f"📅 Дата: {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    await callback.message.edit_text(
        payments_text,
        reply_markup=AdminKeyboard.admin_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "admin:manage_tariffs")
async def manage_tariffs(callback: CallbackQuery):
    # Проверяем, является ли пользователь администратором
    if callback.from_user.id not in config.telegram.admin_ids:
        await callback.answer("У вас нет доступа к этой функции", show_alert=True)
        return
    
    # Получаем все тарифные планы
    tariff_plans = await TariffDAL.get_all_plans()
    
    tariffs_text = f"📝 <b>Управление тарифами</b>\n\n"
    
    for i, plan in enumerate(tariff_plans, 1):
        tariffs_text += (
            f"{i}. <b>{plan.name}</b>\n"
            f"   Цена: {plan.price}₽\n"
            f"   Длительность: {plan.duration_days} дней\n"
            f"   Активен: {'✅' if plan.is_active else '❌'}\n\n"
        )
    
    await callback.message.edit_text(
        tariffs_text,
        reply_markup=AdminKeyboard.manage_tariffs_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "admin:back_to_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    # Возврат в основное админ-меню
    await callback.message.edit_text(
        "👑 Панель администратора", 
        reply_markup=AdminKeyboard.admin_menu()
    )
    await callback.answer()