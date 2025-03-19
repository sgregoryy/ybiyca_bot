from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from src.keyboards.inline import SubscriptionKeyboard
from src.keyboards.reply import MainKeyboard
from src.db.DALS.user import UserDAL
from src.config import config
import logging

router = Router()
logger = logging.getLogger(__name__)


async def check_channel_subscription(bot: Bot, user_id, channel_id):
    """
    Проверяет, подписан ли пользователь на канал
    """
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status not in ["left", "kicked", "banned"]
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        return False


@router.message(Command("start"))
async def cmd_start(message: Message):

    user = await UserDAL.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=f"{message.from_user.first_name} {message.from_user.last_name or ''}",
    )

    if not config.telegram.require_subscription:
        await show_main_menu(message)
        return

    is_subscribed = await check_channel_subscription(
        message.bot, message.from_user.id, config.telegram.sponsor_channel_id
    )

    if not is_subscribed:
        text = """
🔧 MOBIONVIP — ШКОЛА ПРОФЕССИОНАЛЬНОГО РЕМОНТА СМАРТФОНОВ

⚡ МЫ ПРЕВРАЩАЕМ ЛЮБОПЫТСТВО В МАСТЕРСТВО:
• С нуля до первых ремонтов за 2 недели
• Практические навыки от топовых специалистов
• Реальные кейсы и живые примеры

🎯 НАШИ ТРАКТЫ:
• Базовая диагностика устройств
• Замена дисплеев и модулей
• Работа с микросхемами
• Ремонт после попадания воды
• Программирование чипов
• Восстановление данных

💎 ЧТО ПОЛУЧИТ УЧАСТНИК:
• Пошаговые инструкции по ремонту

🛠 ДЛЯ КОГО:
• Начинающих мастеров
• Специалистов среднего уровня
• Владельцев сервисных центров
• Тех, кто хочет работать на себя

🎓 ФОРМАТ ОБУЧЕНИЯ:
• Видеоуроки
• Живые мастер-классы
• Практические задания
• Обратная связь от экспертов
• Закрытый чат единомышленников

💰 ПЕРСПЕКТИВЫ:
• Доход от 200000 руб/мес
• Гибкий график работы
• Возможность открытия своего дела
• Востребованность на рынке

🔥 СТАРТ НОВОГО ПОТОКА СКОРО!
Забронируйте свое место в списке участников
        """
        await message.answer(
            text, reply_markup=SubscriptionKeyboard.subscribe_channel(config.telegram.sponsor_channel_link)
        )
    else:
        await show_main_menu(message)


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):

    if not config.telegram.require_subscription:
        await callback.message.delete()
        await show_main_menu(callback.message)
        await callback.answer("Теперь вы можете пользоваться ботом")
        return

    is_subscribed = await check_channel_subscription(
        callback.bot, callback.from_user.id, config.telegram.sponsor_channel_id
    )

    if is_subscribed:
        await callback.message.delete()
        await show_main_menu(callback.message)
        await callback.answer("Спасибо за подписку! Теперь вы можете пользоваться ботом")
    else:
        await callback.answer("Вы не подписаны на канал. Пожалуйста, подпишитесь, чтобы продолжить", show_alert=True)


async def show_main_menu(message: Message):
    text = f"👋 Добро пожаловать, {message.from_user.first_name}!\n\nВыберите действие из меню"
    await message.answer(text, reply_markup=MainKeyboard.main_menu())
