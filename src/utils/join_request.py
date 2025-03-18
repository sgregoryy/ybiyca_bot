from aiogram import Router, Bot
from aiogram.types import ChatJoinRequest
from src.utils.channel_access import check_user_channel_subscription
from src.db.DALS.channel import ChannelDAL
from src.db.DALS.subscription import SubscriptionDAL
from src.utils.channel_access import process_join_request
import logging

logger = logging.getLogger(__name__)

router = Router()

@router.chat_join_request()
async def handle_join_request(chat_join_request: ChatJoinRequest, bot: Bot):
    """
    Обрабатывает запрос на вступление в канал.
    Проверяет, имеет ли пользователь доступ к каналу согласно своей подписке.
    """
    user_id = chat_join_request.from_user.id
    requested_channel_id = chat_join_request.chat.id
    
    # Получаем канал из базы данных
    channel = await ChannelDAL.get_by_telegram_id(requested_channel_id)
    
    if not channel:
        logger.warning(f"Канал {requested_channel_id} не найден в базе данных")
        # Если канал не найден в базе, отклоняем запрос
        try:
            await chat_join_request.decline()
        except Exception as e:
            logger.error(f"Ошибка при отклонении запроса на вступление: {e}")
        return
    
    # Получаем активную подписку пользователя
    subscription_data = await SubscriptionDAL.get_by_telegram_id(user_id)
    
    if not subscription_data:
        # Нет активной подписки
        try:
            await chat_join_request.decline()
            
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ Для доступа к этому каналу требуется активная подписка.\n\n"
                    "Пожалуйста, оформите подписку через бота, используя команду /start или "
                    "кнопку «💼 Тарифы» в меню бота."
                )
            )
            logger.info(f"Отклонен запрос на вступление в канал {requested_channel_id}: нет активной подписки")
        except Exception as e:
            logger.error(f"Ошибка при отклонении запроса на вступление: {e}")
        return
    
    subscription, plan, _ = subscription_data
    
    # Проверяем, дает ли подписка доступ к запрашиваемому каналу
    if plan.channel_id == channel.id:
        try:
            # Подписка дает доступ к каналу, принимаем запрос
            await chat_join_request.approve()
            logger.info(f"Принят запрос на вступление в канал {requested_channel_id} от пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при принятии запроса на вступление: {e}")
    else:
        try:
            # Подписка не дает доступ к этому каналу
            await chat_join_request.decline()
            
            # Получаем информацию о доступном канале для текущей подписки
            available_channel = await ChannelDAL.get_by_id(plan.channel_id)
            
            message = (
                "❌ Ваша текущая подписка не дает доступ к этому каналу.\n\n"
                f"У вас активна подписка на тариф «{plan.name}», который дает доступ "
                f"к каналу {available_channel.name if available_channel else 'неизвестный канал'}.\n\n"
                "Для доступа к выбранному каналу, пожалуйста, приобретите соответствующий тариф "
                "через команду /start или кнопку «💼 Тарифы» в меню бота."
            )
            
            await bot.send_message(
                chat_id=user_id,
                text=message
            )
            logger.info(f"Отклонен запрос на вступление в канал {requested_channel_id}: нет доступа с текущей подпиской")
        except Exception as e:
            logger.error(f"Ошибка при отклонении запроса на вступление: {e}")