from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from src.filters.admin import AdminFilter
from src.keyboards.inline import AdminKeyboard
from src.utils.states import AdminStates
from src.db.DALS.user import UserDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.tariff import TariffDAL
from src.db.DALS.payment import PaymentDAL
from src.db.DALS.channel import ChannelDAL
from src.config import config
import datetime
import logging
import asyncio

router = Router()
logger = logging.getLogger(__name__)

router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("👑 Панель администратора", reply_markup=AdminKeyboard.admin_menu())


@router.callback_query(F.data == "admin:statistics")
async def show_statistics(callback: CallbackQuery):
    total_users = len(await UserDAL.get_all())

    active_users = await SubscriptionDAL.count_active()

    new_users_today = len(await UserDAL.get_new_users_today())

    pending_payments = await PaymentDAL.count_pending()
    approved_payments = await PaymentDAL.get_revenue_stats()
    total_revenue = approved_payments.get("total_rub", 0)
    payment_count = approved_payments.get("payment_count", 0)

    plan_stats = {}
    if config.admin.manage_tariffs_enabled:
        plan_stats = await SubscriptionDAL.get_plan_statistics()

    stats_text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Активных подписок: {active_users}\n"
        f"🆕 Новых пользователей сегодня: {new_users_today}\n\n"
        f"💰 <b>Статистика платежей:</b>\n"
        f"💸 Всего платежей: {payment_count}\n"
        f"💵 Общий доход: {total_revenue}₽\n"
        f"⏳ Ожидающих проверки: {pending_payments}\n\n"
    )

    if config.admin.manage_tariffs_enabled and plan_stats:
        stats_text += f"📋 <b>Подписки по тарифам:</b>\n"
        for plan_name, count in plan_stats.items():
            stats_text += f"- {plan_name}: {count}\n"

    await callback.message.edit_text(stats_text, reply_markup=AdminKeyboard.admin_menu(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Запуск процесса рассылки сообщений"""
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    await callback.message.answer("📨 Отправьте сообщение, которое хотите разослать всем пользователям.\n")
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Обработка сообщения для рассылки"""
    broadcast_text = message.md_text or message.caption

    if not broadcast_text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение для рассылки")
        return

    await state.update_data(broadcast_text=broadcast_text)

    await message.answer("📋 Предпросмотр сообщения:\n\n" f"{broadcast_text}", parse_mode="MarkdownV2")

    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast:confirm"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast:cancel"),
    )
    builder.adjust(1)

    await message.answer("Выберите действие с сообщением рассылки:", reply_markup=builder.as_markup())


@router.callback_query(F.data == "broadcast:confirm")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и отправка рассылки"""
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")

    if not broadcast_text:
        await callback.answer("Ошибка: текст рассылки не найден", show_alert=True)
        await state.clear()
        return

    await callback.answer("Начинаем рассылку сообщений...")

    progress_message = await callback.message.answer("📨 Начинаем рассылку сообщений...")

    users = await UserDAL.get_active_users()
    total_users = len(users)
    success_count = 0

    for i, user in enumerate(users, 1):
        try:
            if i % 10 == 0 or i == total_users:
                await progress_message.edit_text(
                    f"📨 Отправка сообщений... {i}/{total_users} ({(i/total_users*100):.1f}%)"
                )

            await callback.bot.send_message(chat_id=user.user_id, text=broadcast_text, parse_mode="Markdown")
            success_count += 1

            await asyncio.sleep(0.05)
        except Exception as e:
            if "Forbidden" in str(e):
                logger.error(f"Пользователь {user.user_id} заблокировал бота")
                await UserDAL.mark_inactive(user.user_id)
            elif "retry after" in str(e).lower():
                retry_time = int("".join(filter(str.isdigit, str(e))))
                logger.error(f"Превышен лимит запросов для {user.user_id}. Ожидание {retry_time} секунд.")
                await asyncio.sleep(retry_time)
                try:
                    await callback.bot.send_message(chat_id=user.user_id, text=broadcast_text, parse_mode="Markdown")
                    success_count += 1
                except Exception as inner_e:
                    logger.error(
                        f"Не удалось отправить сообщение пользователю {user.user_id} после ожидания: {inner_e}"
                    )
            else:
                logger.error(f"Не удалось отправить сообщение пользователю {user.user_id}: {e}")

    await state.clear()

    await progress_message.edit_text(
        f"✅ Рассылка завершена.\n" f"Сообщение доставлено {success_count} из {total_users} пользователей."
    )

    await callback.message.edit_text("👑 Панель администратора", reply_markup=AdminKeyboard.admin_menu())


@router.callback_query(F.data == "broadcast:cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    await state.clear()
    await callback.answer("Рассылка отменена")

    await callback.message.edit_text("👑 Панель администратора", reply_markup=AdminKeyboard.admin_menu())


@router.callback_query(F.data == "admin:manage_tariffs")
async def manage_tariffs(callback: CallbackQuery):

    if not config.admin.manage_tariffs_enabled:
        await callback.answer("Функция управления тарифами отключена", show_alert=True)
        return

    tariff_plans = await TariffDAL.get_all_plans()

    tariffs_text = f"📝 <b>Управление тарифами</b>\n\n"

    for i, plan in enumerate(tariff_plans, 1):
        tariffs_text += (
            f"{i}. <b>{plan.name}</b>\n"
            f"   Цена: {plan.price}₽\n"
            f"   Длительность: {plan.duration_days} дней\n"
            f"   Активен: {'✅' if plan.is_active else '❌'}\n\n"
        )

    await callback.message.edit_text(tariffs_text, reply_markup=AdminKeyboard.manage_tariffs_menu(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:manage_channels")
async def manage_channels(callback: CallbackQuery):
    if not config.admin.manage_channels_enabled or not config.channels.multi_channel_mode:
        await callback.answer(
            "Функция управления каналами отключена или бот не настроен на мультиканальный режим", show_alert=True
        )
        return

    channels_with_plans = await ChannelDAL.get_channels_with_plans()

    channels_text = f"📝 <b>Управление каналами доступа</b>\n\n"

    if not channels_with_plans:
        channels_text += "Каналы не найдены. Добавьте первый канал."
    else:
        for i, (channel, plans) in enumerate(channels_with_plans, 1):
            plan_names = [plan.name for plan in plans]
            plans_text = ", ".join(plan_names) if plan_names else "Нет тарифов"

            channels_text += (
                f"{i}. <b>{channel.name}</b>\n"
                f"   ID: {channel.channel_id}\n"
                f"   Активен: {'✅' if channel.is_active else '❌'}\n"
                f"   Тарифы: {plans_text}\n\n"
            )

    await callback.message.edit_text(
        channels_text, reply_markup=AdminKeyboard.manage_channels_menu(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:back_to_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    await callback.message.edit_text("👑 Панель администратора", reply_markup=AdminKeyboard.admin_menu())
    await callback.answer()
