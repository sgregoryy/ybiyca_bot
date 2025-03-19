"""
Data Access Layer для работы с тарифными планами.
"""

from sqlalchemy import select, update, and_, desc, func
from src.db.database import get_db
from src.db.models import TariffPlan
from src.db.DALS.channel import ChannelDAL
from src.config import config
from typing import List, Optional, Dict, Any


class TariffDAL:
    """DAL для работы с тарифными планами"""

    db = get_db()

    @staticmethod
    async def get_by_id(tariff_id: int) -> Optional[TariffPlan]:
        """
        Получить тарифный план по ID

        Args:
            tariff_id: ID тарифного плана

        Returns:
            Тарифный план или None если не найден
        """
        query = select(TariffPlan).where(TariffPlan.id == tariff_id)
        result = await TariffDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_by_code(code: str) -> Optional[TariffPlan]:
        """
        Получить тарифный план по коду

        Args:
            code: Код тарифного плана

        Returns:
            Тарифный план или None если не найден
        """
        query = select(TariffPlan).where(TariffPlan.code == code)
        result = await TariffDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_active_plans() -> List[TariffPlan]:
        """
        Получить все активные тарифные планы

        Returns:
            Список активных тарифных планов
        """
        query = select(TariffPlan).where(TariffPlan.is_active == True).order_by(TariffPlan.display_order)

        result = await TariffDAL.db.fetch(query)
        return [row[0] for row in result]

    @staticmethod
    async def get_tariffs_by_channel(channel_id: int) -> List[TariffPlan]:
        """
        Получить все тарифные планы для конкретного канала

        Args:
            channel_id: ID канала

        Returns:
            Список тарифных планов для канала
        """
        query = (
            select(TariffPlan)
            .where(and_(TariffPlan.channel_id == channel_id, TariffPlan.is_active == True))
            .order_by(TariffPlan.display_order)
        )

        result = await TariffDAL.db.fetch(query)
        return [row[0] for row in result]

    @staticmethod
    async def toggle_active(tariff_id: int) -> Optional[TariffPlan]:
        """
        Переключить статус активности тарифного плана

        Args:
            tariff_id: ID тарифного плана

        Returns:
            Обновленный тарифный план или None если не найден
        """

        tariff = await TariffDAL.get_by_id(tariff_id)
        if not tariff:
            return None

        new_state = not tariff.is_active

        query = update(TariffPlan).where(TariffPlan.id == tariff_id).values(is_active=new_state).returning(TariffPlan)

        result = await TariffDAL.db.execute(query)
        result = result.scalar_one_or_none()
        return result

    @staticmethod
    async def update(tariff_id: int, **kwargs) -> Optional[TariffPlan]:
        """
        Обновить тарифный план

        Args:
            tariff_id: ID тарифного плана
            kwargs: Параметры для обновления

        Returns:
            Обновленный тарифный план или None если не найден
        """

        query = update(TariffPlan).where(TariffPlan.id == tariff_id).values(**kwargs).returning(TariffPlan)

        result = await TariffDAL.db.execute(query)
        result = result.scalar_one_or_none()
        return result

    @staticmethod
    async def initialize_default_plans(
        default_plans: List[Dict[str, Any]], default_channel_id: int = None
    ) -> List[TariffPlan]:
        """
        Инициализировать стандартные тарифные планы

        Args:
            default_plans: Список конфигураций тарифных планов по умолчанию
            default_channel_id: ID канала по умолчанию для всех планов

        Returns:
            Список тарифных планов
        """
        result = []

        if default_channel_id is None:
            return result
        channel_flag = await ChannelDAL.get_by_telegram_id(default_channel_id)

        if not channel_flag:
            channel = await ChannelDAL.create_channel(
                name=config.channels.content_channel_name,
                channel_id=config.channels.content_channel_id,
                invite_link=config.channels.content_channel_link,
            )
            channel_id = channel.id
        else:
            channel_id = 1

        for plan_data in default_plans:

            plan_data_with_channel = plan_data.copy()
            plan_data_with_channel["channel_id"] = channel_id

            plan = await TariffDAL.get_by_code(plan_data["code"])

            if plan is None:

                async with TariffDAL.db.session() as session:
                    plan = TariffPlan(**plan_data_with_channel)
                    session.add(plan)
                    await session.commit()
                    await session.refresh(plan)
            else:

                need_update = False
                update_data = {}

                for key, value in plan_data_with_channel.items():
                    if hasattr(plan, key) and getattr(plan, key) != value:
                        update_data[key] = value
                        need_update = True

                if need_update:

                    query = (
                        update(TariffPlan).where(TariffPlan.id == plan.id).values(**update_data).returning(TariffPlan)
                    )

                    result_row = await TariffDAL.db.fetchrow(query)
                    plan = result_row[0]

            result.append(plan)

        return result

    @staticmethod
    async def get_max_display_order(channel_id: int = None) -> int:
        """
        Получить максимальный порядок отображения

        Args:
            channel_id: ID канала (если указан, то максимальный порядок среди тарифов канала)

        Returns:
            Максимальный порядок отображения
        """
        if channel_id is not None:
            query = select(func.max(TariffPlan.display_order)).where(TariffPlan.channel_id == channel_id)
        else:
            query = select(func.max(TariffPlan.display_order))

        return await TariffDAL.db.fetchval(query) or 0

    @staticmethod
    async def create_tariff(name: str, code: str, price: float, duration_days: int, channel_id: int) -> TariffPlan:
        """
        Создать новый тарифный план для конкретного канала

        Args:
            name: Название тарифного плана
            code: Код тарифного плана
            price: Стоимость тарифного плана
            duration_days: Длительность тарифного плана в днях
            channel_id: ID канала, к которому даёт доступ тариф

        Returns:
            Созданный тарифный план
        """

        max_order = await TariffDAL.get_max_display_order(channel_id) + 1

        async with TariffDAL.db.session() as session:
            plan = TariffPlan(
                name=name,
                code=code,
                price=price,
                duration_days=duration_days,
                channel_id=channel_id,
                is_active=True,
                display_order=max_order,
            )
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            return plan

    @staticmethod
    async def get_all_plans() -> List[TariffPlan]:
        """
        Получить все тарифные планы

        Returns:
            Список всех тарифных планов
        """
        query = select(TariffPlan).order_by(TariffPlan.display_order)
        result = await TariffDAL.db.fetch(query)
        return [row[0] for row in result]
