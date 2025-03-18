import logging
from typing import List, Dict, Any, Optional, Tuple
from aiogram import Bot

from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.channel import ChannelDAL
from src.db.models import Channel

logger = logging.getLogger(__name__)

async def check_user_channel_subscription(bot: Bot, user_id: int, channel_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на указанный канал
    
    Args:
        bot: Объект бота
        user_id: ID пользователя в Telegram
        channel_id: ID канала в Telegram
        
    Returns:
        True если пользователь подписан на канал, False в противном случае
    """
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status not in ["left", "kicked", "banned"]
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки пользователя {user_id} на канал {channel_id}: {e}")
        return False

async def get_user_available_channel(telegram_user_id: int) -> Optional[Channel]:
    """
    Получает канал, к которому пользователь имеет доступ согласно его подписке
    
    Args:
        telegram_user_id: ID пользователя в Telegram
        
    Returns:
        Канал, к которому пользователь имеет доступ, или None
    """
    # Получаем активную подписку пользователя
    subscription_data = await SubscriptionDAL.get_by_telegram_id(telegram_user_id)
    if not subscription_data:
        return None  # Нет активной подписки
    
    subscription, plan, _ = subscription_data
    
    # Получаем канал, к которому дает доступ тарифный план
    channel = await ChannelDAL.get_by_id(plan.channel_id)
    
    return channel

async def check_user_channel_access(telegram_user_id: int, channel_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к каналу согласно его подписке
    
    Args:
        telegram_user_id: ID пользователя в Telegram
        channel_id: ID канала в базе данных
        
    Returns:
        True если пользователь имеет доступ к каналу, False в противном случае
    """
    # Получаем активную подписку пользователя
    subscription_data = await SubscriptionDAL.get_by_telegram_id(telegram_user_id)
    if not subscription_data:
        return False  # Нет активной подписки
    
    subscription, plan, _ = subscription_data
    
    # Проверяем, дает ли тарифный план доступ к запрашиваемому каналу
    return plan.channel_id == channel_id

async def get_user_channel_invite(telegram_user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает ссылку-приглашение в канал, к которому пользователь имеет доступ
    
    Args:
        telegram_user_id: ID пользователя в Telegram
        
    Returns:
        Словарь с информацией о канале (id, name, telegram_id, invite_link) или None
    """
    # Получаем канал, к которому пользователь имеет доступ
    channel = await get_user_available_channel(telegram_user_id)
    
    if not channel:
        return None
    
    return {
        "id": channel.id,
        "name": channel.name,
        "telegram_id": channel.channel_id,
        "invite_link": channel.invite_link
    }

async def check_and_invite_to_channel(bot: Bot, telegram_user_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Проверяет подписку пользователя на доступный ему канал
    
    Args:
        bot: Объект бота
        telegram_user_id: ID пользователя в Telegram
        
    Returns:
        Кортеж (подписан ли пользователь, информация о канале)
    """
    # Получаем канал, к которому пользователь имеет доступ
    channel = await get_user_available_channel(telegram_user_id)
    
    if not channel:
        return False, None
    
    # Проверяем подписку на канал
    is_subscribed = await check_user_channel_subscription(bot, telegram_user_id, channel.channel_id)
    
    channel_info = {
        "id": channel.id,
        "name": channel.name,
        "telegram_id": channel.channel_id,
        "invite_link": channel.invite_link
    }
    
    return is_subscribed, channel_info

async def process_join_request(bot: Bot, user_id: int, requested_channel_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь право на доступ к запрашиваемому каналу
    
    Args:
        bot: Объект бота
        user_id: ID пользователя в Telegram
        requested_channel_id: ID канала в Telegram
        
    Returns:
        True если пользователь имеет доступ, False иначе
    """
    try:
        # Получаем канал из базы данных
        channel = await ChannelDAL.get_by_telegram_id(requested_channel_id)
        if not channel:
            logger.warning(f"Канал {requested_channel_id} не найден в базе данных")
            return False
        
        # Проверяем, имеет ли пользователь доступ к каналу
        has_access = await check_user_channel_access(user_id, channel.id)
        
        if has_access:
            logger.info(f"Пользователь {user_id} имеет доступ к каналу {requested_channel_id}")
        else:
            logger.info(f"Пользователь {user_id} не имеет доступа к каналу {requested_channel_id}")
        
        return has_access
    except Exception as e:
        logger.error(f"Ошибка при проверке доступа к каналу: {e}")
        return False