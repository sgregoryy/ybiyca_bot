"""
Data Access Layer для работы с подписками.
"""

from datetime import datetime, timedelta
from sqlalchemy import select, update, and_, join, func
from src.db.database import get_db
from src.db.models import Subscription, User, TariffPlan
from typing import List, Optional, Tuple, Dict


class SubscriptionDAL:
    """DAL для работы с подписками"""

    db = get_db()

    @staticmethod
    async def get_by_id(subscription_id: int) -> Optional[Subscription]:
        """
        Получить подписку по ID

        Args:
            subscription_id: ID подписки

        Returns:
            Подписка или None если не найдена
        """
        query = select(Subscription).where(Subscription.id == subscription_id)
        result = await SubscriptionDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_active_by_user_id(user_id: int) -> Optional[Tuple[Subscription, TariffPlan]]:
        """
        Получить активную подписку пользователя

        Args:
            user_id: ID пользователя в базе данных

        Returns:
            Кортеж (подписка, тарифный план) или None если подписка не найдена
        """
        query = (
            select(Subscription, TariffPlan)
            .join(TariffPlan, Subscription.plan_id == TariffPlan.id)
            .where(and_(Subscription.user_id == user_id, Subscription.is_active == True))
        )

        result = await SubscriptionDAL.db.fetchrow(query)
        return result if result else None

    @staticmethod
    async def get_by_telegram_id(telegram_id: int) -> Optional[Tuple[Subscription, TariffPlan, User]]:
        """
        Получить активную подписку по Telegram ID

        Args:
            telegram_id: ID пользователя в Telegram

        Returns:
            Кортеж (подписка, тарифный план, пользователь) или None если подписка не найдена
        """
        query = (
            select(Subscription, TariffPlan, User)
            .join(TariffPlan, Subscription.plan_id == TariffPlan.id)
            .join(User, Subscription.user_id == User.id)
            .where(and_(User.user_id == telegram_id, Subscription.is_active == True))
        )

        result = await SubscriptionDAL.db.fetchrow(query)
        return result if result else None

    @staticmethod
    async def create_subscription(user_id: int, plan_id: int) -> Tuple[Subscription, TariffPlan]:
        """
        Создать новую подписку

        Args:
            user_id: ID пользователя в базе данных
            plan_id: ID тарифного плана

        Returns:
            Кортеж (созданная подписка, тарифный план)
        """

        plan_query = select(TariffPlan).where(TariffPlan.id == plan_id)
        plan_result = await SubscriptionDAL.db.fetchrow(plan_query)

        if not plan_result:
            raise ValueError(f"Тарифный план с ID {plan_id} не найден")

        plan = plan_result[0]

        deactivate_query = (
            update(Subscription)
            .where(and_(Subscription.user_id == user_id, Subscription.is_active == True))
            .values(is_active=False)
        )

        await SubscriptionDAL.db.execute(deactivate_query)

        start_date = datetime.now()
        end_date = start_date + timedelta(days=plan.duration_days)

        async with SubscriptionDAL.db.session() as session:
            subscription = Subscription(
                user_id=user_id, plan_id=plan_id, start_date=start_date, end_date=end_date, is_active=True
            )
            session.add(subscription)
            await session.commit()
            await session.refresh(subscription)

        return (subscription, plan)

    @staticmethod
    async def deactivate_expired() -> int:
        """
        Деактивировать истекшие подписки

        Returns:
            Количество деактивированных подписок
        """
        now = datetime.now()

        query = (
            update(Subscription)
            .where(and_(Subscription.is_active == True, Subscription.end_date < now))
            .values(is_active=False)
            .returning(Subscription.id)
        )

        result = await SubscriptionDAL.db.fetch(query)
        return len(result) if result else 0

    @staticmethod
    async def get_expiring_soon(days: int = 3) -> List[Tuple[Subscription, TariffPlan, User]]:
        """
        Получить подписки, истекающие в ближайшее время

        Args:
            days: Количество дней до истечения

        Returns:
            Список кортежей (подписка, тарифный план, пользователь)
        """
        now = datetime.now()
        expiry_date = now + timedelta(days=days)

        query = (
            select(Subscription, TariffPlan, User)
            .join(TariffPlan, Subscription.plan_id == TariffPlan.id)
            .join(User, Subscription.user_id == User.id)
            .where(
                and_(Subscription.is_active == True, Subscription.end_date <= expiry_date, Subscription.end_date >= now)
            )
        )

        result = await SubscriptionDAL.db.fetch(query)
        return result if result else []

    @staticmethod
    async def extend_subscription(subscription_id: int, days: int) -> Optional[Subscription]:
        """
        Продлить подписку на указанное количество дней

        Args:
            subscription_id: ID подписки
            days: Количество дней для продления

        Returns:
            Обновленная подписка или None если подписка не найдена
        """
        subscription = await SubscriptionDAL.get_by_id(subscription_id)
        if not subscription:
            return None

        if subscription.end_date < datetime.now():
            new_end_date = datetime.now() + timedelta(days=days)
        else:
            new_end_date = subscription.end_date + timedelta(days=days)

        query = (
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(end_date=new_end_date, is_active=True)
            .returning(Subscription)
        )

        result = await SubscriptionDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_plan_statistics() -> Dict[str, int]:
        """
        Получить статистику активных подписок по тарифным планам

        Returns:
            Словарь с названиями тарифных планов в качестве ключей и количеством подписок в качестве значений
        """
        query = (
            select(TariffPlan.name, func.count(Subscription.id).label("count"))
            .join(Subscription, TariffPlan.id == Subscription.plan_id)
            .where(Subscription.is_active == True)
            .group_by(TariffPlan.name)
        )

        result = await SubscriptionDAL.db.fetch(query)

        stats = {}
        for row in result:
            stats[row[0]] = row[1]

        return stats

    @staticmethod
    async def count_active() -> int:
        """
        Подсчитать количество активных подписок

        Returns:
            Количество активных подписок
        """
        query = select(func.count()).select_from(Subscription).where(Subscription.is_active == True)
        return await SubscriptionDAL.db.fetchval(query) or 0

    @staticmethod
    async def get_expired_active() -> List[Tuple[Subscription, TariffPlan, User]]:
        """
        Получить истекшие активные подписки

        Returns:
            Список кортежей (подписка, тарифный план, пользователь)
        """
        now = datetime.now()

        query = (
            select(Subscription, TariffPlan, User)
            .join(TariffPlan, Subscription.plan_id == TariffPlan.id)
            .join(User, Subscription.user_id == User.id)
            .where(and_(Subscription.is_active == True, Subscription.end_date < now))
        )

        result = await SubscriptionDAL.db.fetch(query)
        return result if result else []

    @staticmethod
    async def deactivate_subscription(subscription_id: int) -> bool:
        """
        Деактивировать подписку

        Args:
            subscription_id: ID подписки

        Returns:
            True если подписка успешно деактивирована, False в противном случае
        """
        query = (
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(is_active=False)
            .returning(Subscription.id)
        )

        result = await SubscriptionDAL.db.fetchval(query)
        return result is not None
