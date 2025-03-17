"""
Data Access Layer для работы с пользователями.
"""

from datetime import datetime
from sqlalchemy import select, update, and_, func
from src.db.database import get_db
from src.db.models import User
from typing import List, Optional


class UserDAL:
    """DAL для работы с пользователями"""
    db = get_db()
    
    @staticmethod
    async def get_by_telegram_id(telegram_id: int) -> Optional[User]:
        """
        Получить пользователя по Telegram ID
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            Пользователь или None если не найден
        """
        query = select(User).where(User.user_id == telegram_id)
        result = await UserDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def get_or_create(telegram_id: int, username: Optional[str], full_name: str) -> User:
        """
        Получить или создать пользователя
        
        Args:
            telegram_id: ID пользователя в Telegram
            username: Username пользователя
            full_name: Полное имя пользователя
            
        Returns:
            Объект пользователя
        """
        # Сначала проверяем, существует ли пользователь
        result = await UserDAL.db.fetchrow(select(User).where(User.user_id == telegram_id))
        
        if not result:
            # Если пользователь не найден, создаем нового
            async with UserDAL.db.session() as session:
                user = User(
                    user_id=telegram_id,
                    username=username,
                    full_name=full_name,
                    is_active=True,
                    created_at=datetime.now()
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user
        
        user = result[0]
        
        # Проверяем, нужно ли обновить данные пользователя
        need_update = False
        update_data = {}
        
        if user.username != username:
            update_data["username"] = username
            need_update = True
            
        if user.full_name != full_name:
            update_data["full_name"] = full_name
            need_update = True
        
        # Если пользователь неактивен, активируем его
        if not user.is_active:
            update_data["is_active"] = True
            need_update = True
        
        if need_update:
            # Обновляем данные пользователя
            query = (
                update(User)
                .where(User.user_id == telegram_id)
                .values(**update_data)
                .returning(User)
            )
            
            result = await UserDAL.db.fetchrow(query)
            return result[0]
        
        return user
    
    @staticmethod
    async def get_active_users() -> List[User]:
        """
        Получить всех активных пользователей
        
        Returns:
            Список активных пользователей
        """
        query = select(User).where(User.is_active == True)
        result = await UserDAL.db.fetch(query)
        return [row[0] for row in result]
    
    @staticmethod
    async def get_new_users_today() -> List[User]:
        """
        Получить пользователей, зарегистрированных сегодня
        
        Returns:
            Список новых пользователей
        """
        today = datetime.now().date()
        query = select(User).where(User.created_at >= today)
        result = await UserDAL.db.fetch(query)
        return [row[0] for row in result]
    
    @staticmethod
    async def mark_inactive(telegram_id: int) -> bool:
        """
        Отметить пользователя как неактивного
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            True если пользователь был отмечен неактивным, False в противном случае
        """
        query = (
            update(User)
            .where(User.user_id == telegram_id)
            .values(is_active=False)
            .returning(User.id)
        )
        
        result = await UserDAL.db.fetchval(query)
        return result is not None
    
    @staticmethod
    async def count_active() -> int:
        """
        Подсчитать количество активных пользователей
        
        Returns:
            Количество активных пользователей
        """
        query = select(func.count()).select_from(User).where(User.is_active == True)
        return await UserDAL.db.fetchval(query) or 0
    
    @staticmethod
    async def get_by_id(user_id: int) -> Optional[User]:
        """
        Получить пользователя по ID в базе данных
        
        Args:
            user_id: ID пользователя в базе данных
            
        Returns:
            Пользователь или None если не найден
        """
        query = select(User).where(User.id == user_id)
        result = await UserDAL.db.fetchrow(query)
        return result[0] if result else None