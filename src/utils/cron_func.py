import logging
from datetime import datetime, timedelta
from aiogram import Bot
from sqlalchemy import and_, select, update

from src.db.DALS.subscription import SubscriptionDAL
from src.db.DALS.tariff import TariffDAL
from src.db.DALS.channel import ChannelDAL
from src.db.DALS.user import UserDAL
from src.db.models import Subscription, TariffPlan, User
from src.config import config

logger = logging.getLogger(__name__)


async def check_expired_subscriptions(bot: Bot):
    """
    Check for expired subscriptions, notify users, and remove them from channels
    """
    now = datetime.now()

    query = (
        select(Subscription, TariffPlan, User)
        .join(TariffPlan, Subscription.plan_id == TariffPlan.id)
        .join(User, Subscription.user_id == User.id)
        .where(and_(Subscription.is_active == True, Subscription.end_date < now))
    )

    expired_subscriptions = await SubscriptionDAL.db.fetch(query)

    if not expired_subscriptions:
        logger.info("No expired subscriptions found")
        return

    for row in expired_subscriptions:
        subscription, plan, user = row
        try:

            await SubscriptionDAL.db.execute(
                update(Subscription).where(Subscription.id == subscription.id).values(is_active=False)
            )

            channel = await ChannelDAL.get_by_id(plan.channel_id)

            if channel and channel.is_active:
                try:

                    await bot.ban_chat_member(chat_id=channel.channel_id, user_id=user.user_id)

                    await bot.unban_chat_member(chat_id=channel.channel_id, user_id=user.user_id, only_if_banned=True)
                    logger.info(f"User {user.user_id} removed from channel {channel.channel_id}")
                except Exception as e:
                    logger.error(f"Failed to remove user {user.user_id} from channel {channel.channel_id}: {e}")

            message_text = (
                f"📅 Ваша подписка на тариф «{plan.name}» истекла.\n\n"
                f"Для продления доступа, пожалуйста, выберите тариф с помощью команды /start или "
                f"нажмите на кнопку «💼 Тарифы» в меню бота."
            )

            await bot.send_message(chat_id=user.user_id, text=message_text)

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
    now = datetime.now()
    threshold_date = now + timedelta(days=days_threshold)

    query = (
        select(Subscription, TariffPlan, User)
        .join(TariffPlan, Subscription.plan_id == TariffPlan.id)
        .join(User, Subscription.user_id == User.id)
        .where(
            and_(Subscription.is_active == True, Subscription.end_date <= threshold_date, Subscription.end_date > now)
        )
    )

    ending_soon = await SubscriptionDAL.db.fetch(query)

    if not ending_soon:
        logger.info(f"No subscriptions expiring in {days_threshold} days found")
        return

    for row in ending_soon:
        subscription, plan, user = row
        try:

            days_word = "день"
            if 2 <= days_threshold <= 4:
                days_word = "дня"
            elif days_threshold >= 5:
                days_word = "дней"

            message_text = (
                f"⚠️ Ваша подписка на тариф «{plan.name}» истечет через {days_threshold} {days_word}.\n\n"
                f"Чтобы продлить доступ, воспользуйтесь командой /start или "
                f"нажмите на кнопку «💼 Тарифы» в меню бота."
            )

            await bot.send_message(chat_id=user.user_id, text=message_text)

            logger.info(f"Notification about subscription expiration sent to user {user.user_id}")

        except Exception as e:
            logger.error(f"Error sending expiration notification to user {user.user_id}: {e}")
