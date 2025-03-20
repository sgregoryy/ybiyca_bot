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
        with open("welcome_message.txt", "r", encoding="utf-8") as f:
            welcome_template = f.read().strip()
            text =  welcome_template + '\n\nДля использования бота нужно подписаться на канал'
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
    # Try to read custom welcome message from file
    try:
        with open("welcome_message.txt", "r", encoding="utf-8") as f:
            welcome_template = f.read().strip()
            text =  welcome_template
    except:
        welcome_template = "👋 Добро пожаловать, {first_name}!\n\nВыберите действие из меню"
        text = welcome_template.format(first_name=message.from_user.first_name)
    
    # Insert user's first name
    
    
    await message.answer(text, reply_markup=MainKeyboard.main_menu())