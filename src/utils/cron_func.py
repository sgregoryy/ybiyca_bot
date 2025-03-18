"""
Utilities for checking subscription status, expiration, and managing notifications.
"""

import logging
from datetime import datetime, timedelta
from aiogram import Bot
from sqlalchemy import and_, or_, select

from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.tariff import TariffDAL
from src.db.DALS.channel import ChannelDAL
from src.db.DALS.user import UserDAL
from src.db.models import Subscription, TariffPlan, Channel, User
from src.config import config

logger = logging.getLogger(__name__)

async def check_expired_subscriptions(bot: Bot):
    """
    Check for expired subscriptions, notify users, and remove them from channels
    """

    expired_subscriptions = await SubscriptionDAL.get_expired_active()
    
    for subscription, plan, user in expired_subscriptions:
        try:

            await SubscriptionDAL.deactivate_subscription(subscription.id)

            channels = await ChannelDAL.get_channels_by_plan(plan.id)
            

            for channel in channels:
                try:
                    if channel.is_active:
                        await bot.ban_chat_member(
                            chat_id=channel.channel_id,
                            user_id=user.user_id
                        )

                        await bot.unban_chat_member(
                            chat_id=channel.channel_id,
                            user_id=user.user_id,
                            only_if_banned=True
                        )
                        logger.info(f"User {user.user_id} removed from channel {channel.channel_id}")
                except Exception as e:
                    logger.error(f"Failed to remove user {user.user_id} from channel {channel.channel_id}: {e}")
            

            message_text = (
                f"📅 Ваша подписка на тариф «{plan.name}» истекла.\n\n"
                f"Для продления доступа, пожалуйста, выберите тариф с помощью команды /start или "
                f"нажмите на кнопку «💼 Тарифы» в меню бота."
            )
            

            await bot.send_message(
                chat_id=user.user_id,
                text=message_text
            )
            
            logger.info(f"Subscription for user {user.user_id} has expired and been deactivated.")
            
        except Exception as e:
            logger.error(f"Error processing expired subscription for user {user.user_id}: {e}")


async def check_subscriptions_ending_soon(bot: Bot, days_threshold: int = 1):
    """
    Check for subscriptions that will expire soon and notify users
    
    Args:
        bot: Bot instance
        days_threshold: Number of days before expiration to send notification
    """

    ending_soon = await SubscriptionDAL.get_expiring_soon(days_threshold)
    
    for subscription, plan, user in ending_soon:
        try:

            message_text = (
                f"⚠️ Ваша подписка на тариф «{plan.name}» истечет через {days_threshold} "
                f"{'день' if days_threshold == 1 else 'дня' if 2 <= days_threshold <= 4 else 'дней'}.\n\n"
                f"Чтобы продлить доступ, воспользуйтесь командой /start или "
                f"нажмите на кнопку «💼 Тарифы» в меню бота."
            )

            await bot.send_message(
                chat_id=user.user_id,
                text=message_text
            )
            
            logger.info(f"Notification about subscription expiration sent to user {user.user_id}")
            
        except Exception as e:
            logger.error(f"Error sending expiration notification to user {user.user_id}: {e}")


async def process_join_request(bot: Bot, user_id: int, requested_channel_id: int):
    """
    Process a join request to a channel
    
    Args:
        bot: Bot instance
        user_id: User's Telegram ID
        requested_channel_id: Channel's Telegram ID
        
    Returns:
        bool: True if user has access to the channel, False otherwise
    """
    try:

        user = await UserDAL.get_by_telegram_id(user_id)
        if not user:
            logger.warning(f"User {user_id} not found when processing join request")
            return False
        

        channel = await ChannelDAL.get_by_telegram_id(requested_channel_id)
        if not channel:
            logger.warning(f"Channel {requested_channel_id} not found when processing join request")
            return False
        

        subscription_data = await SubscriptionDAL.get_by_telegram_id(user_id)
        if not subscription_data:
            logger.info(f"No active subscription found for user {user_id}")
            return False
        
        subscription, plan, _ = subscription_data
        

        has_access = await ChannelDAL.check_plan_has_access_to_channel(plan.id, channel.id)
        
        if has_access:
            logger.info(f"User {user_id} has access to channel {requested_channel_id}")
            return True
        else:
            logger.info(f"User {user_id} does not have access to channel {requested_channel_id} with current plan")
            return False
            
    except Exception as e:
        logger.error(f"Error processing join request for user {user_id} to channel {requested_channel_id}: {e}")
        return False