from sqlalchemy import select, update, and_, desc, func, delete
from src.db.database import get_db
from src.db.models import Channel, TariffPlan, User, Subscription
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
        # Сначала получаем все тарифы, относящиеся к каналу
        tariffs_query = select(TariffPlan).where(TariffPlan.channel_id == channel_id)
        tariffs_result = await ChannelDAL.db.fetch(tariffs_query)
        tariff_ids = [row[0].id for row in tariffs_result]
        
        # Проверяем наличие активных подписок на тарифы этого канала
        has_active_subscriptions = False
        for tariff_id in tariff_ids:
            subs_query = select(Subscription).where(
                and_(
                    Subscription.plan_id == tariff_id,
                    Subscription.is_active == True
                )
            )
            result = await ChannelDAL.db.fetchrow(subs_query)
            if result:
                has_active_subscriptions = True
                break
        
        if has_active_subscriptions:
            # Если есть активные подписки, просто деактивируем канал
            update_query = (
                update(Channel)
                .where(Channel.id == channel_id)
                .values(is_active=False)
                .returning(Channel.id)
            )
            result = await ChannelDAL.db.fetchval(update_query)
            return result is not None
        else:
            # Если нет активных подписок, можно удалить канал
            # и деактивировать связанные тарифы
            for tariff_id in tariff_ids:
                update_tariff_query = (
                    update(TariffPlan)
                    .where(TariffPlan.id == tariff_id)
                    .values(is_active=False)
                )
                await ChannelDAL.db.execute(update_tariff_query)
            
            # Затем удаляем сам канал
            delete_query = delete(Channel).where(Channel.id == channel_id).returning(Channel.id)
            result = await ChannelDAL.db.fetchval(delete_query)
            return result is not None
    
    @staticmethod
    async def get_channels_with_tariffs() -> List[Tuple[Channel, List[TariffPlan]]]:
        """
        Получить все каналы с их тарифными планами
        
        Returns:
            Список кортежей (канал, список тарифных планов)
        """
        # Получаем все каналы
        channels = await ChannelDAL.get_all_channels()
        result = []
        
        for channel in channels:
            # Получаем тарифные планы для канала напрямую
            tariffs_query = (
                select(TariffPlan)
                .where(and_(
                    TariffPlan.channel_id == channel.id,
                    TariffPlan.is_active == True
                ))
                .order_by(TariffPlan.display_order)
            )
            
            tariffs_result = await ChannelDAL.db.fetch(tariffs_query)
            tariffs = [row[0] for row in tariffs_result]
            
            result.append((channel, tariffs))
        
        return result
    
    async def get_channels_with_plans() -> List[Tuple[Channel, List[TariffPlan]]]:
        """
        Получить все каналы с их тарифными планами
        
        Returns:
            Список кортежей (канал, список тарифных планов)
        """
        # Получаем все каналы
        channels = await ChannelDAL.get_all_channels()
        result = []
        
        for channel in channels:
            # Получаем тарифные планы для канала напрямую
            tariffs_query = (
                select(TariffPlan)
                .where(and_(
                    TariffPlan.channel_id == channel.id,
                    TariffPlan.is_active == True
                ))
                .order_by(TariffPlan.display_order)
            )
            
            tariffs_result = await ChannelDAL.db.fetch(tariffs_query)
            tariffs = [row[0] for row in tariffs_result]
            
            result.append((channel, tariffs))
        
        return result
    
    @staticmethod
    async def check_user_has_access_to_channel(telegram_user_id: int, channel_id: int) -> bool:
        """
        Проверяет, имеет ли пользователь доступ к указанному каналу
        
        Args:
            telegram_user_id: ID пользователя в Telegram
            channel_id: ID канала в базе данных
            
        Returns:
            True если пользователь имеет доступ к каналу, False в противном случае
        """
        # Получаем активную подписку пользователя для данного канала
        query = (
            select(Subscription)
            .join(User, Subscription.user_id == User.id)
            .join(TariffPlan, Subscription.plan_id == TariffPlan.id)
            .where(and_(
                User.user_id == telegram_user_id,
                Subscription.is_active == True,
                TariffPlan.channel_id == channel_id
            ))
        )
        
        result = await ChannelDAL.db.fetchrow(query)
        return result is not None
    
    @staticmethod
    async def get_user_available_channels(telegram_user_id: int) -> List[Channel]:
        """
        Получает список каналов, к которым пользователь имеет доступ согласно его подпискам
        
        Args:
            telegram_user_id: ID пользователя в Telegram
            
        Returns:
            Список каналов, к которым пользователь имеет доступ
        """
        # Получаем каналы, связанные с активными подписками пользователя
        query = (
            select(Channel)
            .join(TariffPlan, Channel.id == TariffPlan.channel_id)
            .join(Subscription, TariffPlan.id == Subscription.plan_id)
            .join(User, Subscription.user_id == User.id)
            .where(and_(
                User.user_id == telegram_user_id,
                Subscription.is_active == True,
                Channel.is_active == True
            ))
            .order_by(Channel.display_order)
        )
        
        result = await ChannelDAL.db.fetch(query)
        return [row[0] for row in result]