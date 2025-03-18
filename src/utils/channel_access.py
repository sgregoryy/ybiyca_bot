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

async def get_user_available_channels(telegram_user_id: int) -> List[Channel]:
    """
    Получает список каналов, к которым пользователь имеет доступ согласно его подписке
    
    Args:
        telegram_user_id: ID пользователя в Telegram
        
    Returns:
        Список каналов, к которым пользователь имеет доступ
    """
    # Получаем активную подписку пользователя
    subscription_data = await SubscriptionDAL.get_by_telegram_id(telegram_user_id)
    if not subscription_data:
        return []  # Нет активной подписки
    
    subscription, plan, _ = subscription_data
    
    # Получаем каналы, доступные по тарифному плану
    channels = await ChannelDAL.get_channels_by_plan(plan.id)
    
    return channels

async def check_user_channel_access(telegram_user_id: int, channel_id: int) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к каналу согласно его подписке
    
    Args:
        telegram_user_id: ID пользователя в Telegram
        channel_id: ID канала в базе данных
        
    Returns:
        True если пользователь имеет доступ к каналу, False в противном случае
    """
    # Получаем доступные каналы
    available_channels = await get_user_available_channels(telegram_user_id)
    
    # Проверяем, есть ли нужный канал в списке доступных
    return any(channel.id == channel_id for channel in available_channels)

async def get_user_channel_invites(telegram_user_id: int) -> List[Dict[str, Any]]:
    """
    Получает список ссылок-приглашений в каналы, к которым пользователь имеет доступ
    
    Args:
        telegram_user_id: ID пользователя в Telegram
        
    Returns:
        Список словарей с информацией о каналах (id, name, invite_link)
    """
    # Получаем каналы, к которым пользователь имеет доступ
    channels = await get_user_available_channels(telegram_user_id)
    
    # Формируем список ссылок-приглашений
    invites = []
    for channel in channels:
        invites.append({
            "id": channel.id,
            "name": channel.name,
            "telegram_id": channel.channel_id,
            "invite_link": channel.invite_link
        })
    
    return invites

async def check_and_invite_to_channels(bot: Bot, telegram_user_id: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Проверяет подписку пользователя на доступные ему каналы и возвращает списки
    каналов, на которые пользователь уже подписан, и каналов, на которые ему нужно подписаться
    
    Args:
        bot: Объект бота
        telegram_user_id: ID пользователя в Telegram
        
    Returns:
        Кортеж из двух списков: каналы, на которые пользователь уже подписан, и каналы,
        на которые пользователю нужно подписаться
    """
    # Получаем каналы, к которым пользователь имеет доступ
    available_channels = await get_user_available_channels(telegram_user_id)
    
    subscribed_channels = []
    need_to_subscribe_channels = []
    
    # Проверяем подписку на каждый канал
    for channel in available_channels:
        is_subscribed = await check_user_channel_subscription(bot, telegram_user_id, channel.channel_id)
        
        channel_info = {
            "id": channel.id,
            "name": channel.name,
            "telegram_id": channel.channel_id,
            "invite_link": channel.invite_link
        }
        
        if is_subscribed:
            subscribed_channels.append(channel_info)
        else:
            need_to_subscribe_channels.append(channel_info)
    
    return subscribed_channels, need_to_subscribe_channels