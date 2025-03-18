"""
Data Access Layer для работы с каналами доступа.
"""

from sqlalchemy import select, update, and_, desc, func, delete
from src.db.database import get_db
from src.db.models import Channel, ChannelAccessPlan, TariffPlan
from typing import List, Optional, Dict, Any, Tuple


class ChannelDAL:
    """DAL для работы с каналами доступа"""
    db = get_db()
    
    @staticmethod
    async def get_by_id(channel_id: int) -> Optional[Channel]:
        """
        Получить канал по ID
        
        Args:
            channel_id: ID канала
            
        Returns:
            Канал или None если не найден
        """
        query = select(Channel).where(Channel.id == channel_id)
        result = await ChannelDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def get_by_telegram_id(telegram_id: int) -> Optional[Channel]:
        """
        Получить канал по Telegram ID
        
        Args:
            telegram_id: ID канала в Telegram
            
        Returns:
            Канал или None если не найден
        """
        query = select(Channel).where(Channel.channel_id == telegram_id)
        result = await ChannelDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def get_active_channels() -> List[Channel]:
        """
        Получить все активные каналы
        
        Returns:
            Список активных каналов
        """
        query = (
            select(Channel)
            .where(Channel.is_active == True)
            .order_by(Channel.display_order)
        )
        
        result = await ChannelDAL.db.fetch(query)
        return [row[0] for row in result]
    
    @staticmethod
    async def toggle_active(channel_id: int) -> Optional[Channel]:
        """
        Переключить статус активности канала
        
        Args:
            channel_id: ID канала
            
        Returns:
            Обновленный канал или None если не найден
        """
        # Получаем текущее состояние
        channel = await ChannelDAL.get_by_id(channel_id)
        if not channel:
            return None
            
        new_state = not channel.is_active
        
        # Обновляем состояние
        query = (
            update(Channel)
            .where(Channel.id == channel_id)
            .values(is_active=new_state)
            .returning(Channel)
        )
        
        result = await ChannelDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def initialize_default_channels(default_channels: List[Dict[str, Any]]) -> List[Channel]:
        """
        Инициализировать стандартные каналы
        
        Args:
            default_channels: Список конфигураций каналов по умолчанию
            
        Returns:
            Список каналов
        """
        result = []
        
        for channel_data in default_channels:
            # Проверяем, существует ли канал с таким Telegram ID
            channel = await ChannelDAL.get_by_telegram_id(channel_data["channel_id"])
            
            if channel is None:
                # Создаем новый канал
                async with ChannelDAL.db.session() as session:
                    channel = Channel(**channel_data)
                    session.add(channel)
                    await session.commit()
                    await session.refresh(channel)
            else:
                # Проверяем, нужно ли обновить данные
                need_update = False
                update_data = {}
                
                for key, value in channel_data.items():
                    if hasattr(channel, key) and getattr(channel, key) != value:
                        update_data[key] = value
                        need_update = True
                
                if need_update:
                    # Обновляем данные канала
                    query = (
                        update(Channel)
                        .where(Channel.id == channel.id)
                        .values(**update_data)
                        .returning(Channel)
                    )
                    
                    result_row = await ChannelDAL.db.fetchrow(query)
                    channel = result_row[0]
            
            result.append(channel)
        
        return result
    
    @staticmethod
    async def get_max_display_order() -> int:
        """
        Получить максимальный порядок отображения
        
        Returns:
            Максимальный порядок отображения
        """
        query = select(func.max(Channel.display_order))
        return await ChannelDAL.db.fetchval(query) or 0
    
    @staticmethod
    async def create_channel(
        name: str, 
        channel_id: int, 
        invite_link: str,
        display_order: Optional[int] = None
    ) -> Channel:
        """
        Создать новый канал
        
        Args:
            name: Название канала
            channel_id: ID канала в Telegram
            invite_link: Ссылка-приглашение в канал
            display_order: Порядок отображения
            
        Returns:
            Созданный канал
        """
        # Получаем максимальный порядок отображения, если не указан
        if display_order is None:
            display_order = await ChannelDAL.get_max_display_order() + 1
        
        # Создаем новый канал
        async with ChannelDAL.db.session() as session:
            channel = Channel(
                name=name,
                channel_id=channel_id,
                invite_link=invite_link,
                is_active=True,
                display_order=display_order
            )
            session.add(channel)
            await session.commit()
            await session.refresh(channel)
            return channel
    
    @staticmethod
    async def update_channel(
        channel_id: int,
        **kwargs
    ) -> Optional[Channel]:
        """
        Обновить канал
        
        Args:
            channel_id: ID канала
            kwargs: Параметры для обновления
            
        Returns:
            Обновленный канал или None если не найден
        """
        # Обновляем канал
        query = (
            update(Channel)
            .where(Channel.id == channel_id)
            .values(**kwargs)
            .returning(Channel)
        )
        
        result = await ChannelDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def get_all_channels() -> List[Channel]:
        """
        Получить все каналы
        
        Returns:
            Список всех каналов
        """
        query = select(Channel).order_by(Channel.display_order)
        result = await ChannelDAL.db.fetch(query)
        return [row[0] for row in result]
    
    @staticmethod
    async def delete_channel(channel_id: int) -> bool:
        """
        Удалить канал
        
        Args:
            channel_id: ID канала
            
        Returns:
            True если канал удален, False в противном случае
        """
        # Сначала удаляем связи с тарифными планами
        delete_access_query = delete(ChannelAccessPlan).where(ChannelAccessPlan.channel_id == channel_id)
        await ChannelDAL.db.execute(delete_access_query)
        
        # Затем удаляем сам канал
        delete_query = delete(Channel).where(Channel.id == channel_id).returning(Channel.id)
        result = await ChannelDAL.db.fetchval(delete_query)
        return result is not None
    
    @staticmethod
    async def get_channels_by_plan(plan_id: int) -> List[Channel]:
        """
        Получить каналы, доступные по тарифному плану
        
        Args:
            plan_id: ID тарифного плана
            
        Returns:
            Список каналов, доступных по данному тарифному плану
        """
        query = (
            select(Channel)
            .join(ChannelAccessPlan, Channel.id == ChannelAccessPlan.channel_id)
            .where(and_(
                ChannelAccessPlan.plan_id == plan_id,
                Channel.is_active == True
            ))
            .order_by(Channel.display_order)
        )
        
        result = await ChannelDAL.db.fetch(query)
        return [row[0] for row in result]
    
    @staticmethod
    async def get_channels_with_plans() -> List[Tuple[Channel, List[TariffPlan]]]:
        """
        Получить все каналы с привязанными к ним тарифными планами
        
        Returns:
            Список кортежей (канал, список тарифных планов)
        """
        # Получаем все каналы
        channels = await ChannelDAL.get_all_channels()
        result = []
        
        for channel in channels:
            # Получаем тарифные планы для канала
            plans_query = (
                select(TariffPlan)
                .join(ChannelAccessPlan, TariffPlan.id == ChannelAccessPlan.plan_id)
                .where(ChannelAccessPlan.channel_id == channel.id)
                .order_by(TariffPlan.display_order)
            )
            
            plans_result = await ChannelDAL.db.fetch(plans_query)
            plans = [row[0] for row in plans_result]
            
            result.append((channel, plans))
        
        return result
    
    @staticmethod
    async def add_plan_to_channel(channel_id: int, plan_id: int) -> Optional[ChannelAccessPlan]:
        """
        Добавить тарифный план к каналу
        
        Args:
            channel_id: ID канала
            plan_id: ID тарифного плана
            
        Returns:
            Созданный объект доступа или None в случае ошибки
        """
        # Проверяем, существует ли уже такая связь
        query = (
            select(ChannelAccessPlan)
            .where(and_(
                ChannelAccessPlan.channel_id == channel_id,
                ChannelAccessPlan.plan_id == plan_id
            ))
        )
        
        existing = await ChannelDAL.db.fetchrow(query)
        if existing:
            return existing[0]
        
        # Создаем новую связь
        async with ChannelDAL.db.session() as session:
            access_plan = ChannelAccessPlan(
                channel_id=channel_id,
                plan_id=plan_id
            )
            session.add(access_plan)
            await session.commit()
            await session.refresh(access_plan)
            return access_plan
    
    @staticmethod
    async def remove_plan_from_channel(channel_id: int, plan_id: int) -> bool:
        """
        Удалить тарифный план из канала
        
        Args:
            channel_id: ID канала
            plan_id: ID тарифного плана
            
        Returns:
            True если связь удалена, False в противном случае
        """
        query = delete(ChannelAccessPlan).where(
            and_(
                ChannelAccessPlan.channel_id == channel_id,
                ChannelAccessPlan.plan_id == plan_id
            )
        ).returning(ChannelAccessPlan.id)
        
        result = await ChannelDAL.db.fetchval(query)
        return result is not None
    
    @staticmethod
    async def get_plans_for_channel(channel_id: int) -> List[TariffPlan]:
        """
        Получить все тарифные планы, связанные с каналом
        
        Args:
            channel_id: ID канала
            
        Returns:
            Список тарифных планов
        """
        query = (
            select(TariffPlan)
            .join(ChannelAccessPlan, TariffPlan.id == ChannelAccessPlan.plan_id)
            .where(ChannelAccessPlan.channel_id == channel_id)
            .order_by(TariffPlan.display_order)
        )
        
        result = await ChannelDAL.db.fetch(query)
        return [row[0] for row in result]
    
    @staticmethod
    async def update_channel_plans(channel_id: int, plan_ids: List[int]) -> bool:
        """
        Обновить список тарифных планов для канала
        
        Args:
            channel_id: ID канала
            plan_ids: Список ID тарифных планов
            
        Returns:
            True если обновление успешно, False в противном случае
        """
        try:
            delete_query = delete(ChannelAccessPlan).where(ChannelAccessPlan.channel_id == channel_id)
            await ChannelDAL.db.execute(delete_query)

            for plan_id in plan_ids:
                await ChannelDAL.add_plan_to_channel(channel_id, plan_id)
                
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Ошибка при обновлении планов для канала {channel_id}: {e}")
            return False
        
    @staticmethod
    async def check_plan_has_access_to_channel(plan_id: int, channel_id: int) -> bool:
        """
        Проверяет, имеет ли тарифный план доступ к указанному каналу
        
        Args:
            plan_id: ID тарифного плана
            channel_id: ID канала в базе данных
            
        Returns:
            True если тарифный план имеет доступ к каналу, False в противном случае
        """
        query = select(ChannelAccessPlan).where(
            and_(
                ChannelAccessPlan.plan_id == plan_id,
                ChannelAccessPlan.channel_id == channel_id
            )
        )
        
        result = await ChannelDAL.db.fetchrow(query)
        return result is not None