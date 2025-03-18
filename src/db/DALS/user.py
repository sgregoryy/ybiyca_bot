"""
Data Access Layer for working with users.
"""

from datetime import datetime
from sqlalchemy import select, update, and_, func
from src.db.database import get_db
from src.db.models import User
from src.config import config
from typing import List, Optional


class UserDAL:
    """DAL для работы с пользователями"""

    db = get_db()

    @staticmethod
    async def get_by_telegram_id(telegram_id: int) -> Optional[User]:
        """
        Get user by Telegram ID

        Args:
            telegram_id: User's Telegram ID

        Returns:
            User or None if not found
        """
        query = select(User).where(User.user_id == telegram_id)
        result = await UserDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_or_create(
        telegram_id: int, username: Optional[str], full_name: str, language: Optional[str] = None
    ) -> User:
        """
        Get or create user

        Args:
            telegram_id: User's Telegram ID
            username: User's username
            full_name: User's full name
            language: User's preferred language

        Returns:
            User object
        """

        result = await UserDAL.db.fetchrow(select(User).where(User.user_id == telegram_id))

        if not result:

            async with UserDAL.db.session() as session:
                user = User(
                    user_id=telegram_id,
                    username=username,
                    full_name=full_name,
                    is_active=True,
                    created_at=datetime.now(),
                    language=language or config.localization.default_language,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user

        user = result[0]

        need_update = False
        update_data = {}

        if user.username != username:
            update_data["username"] = username
            need_update = True

        if user.full_name != full_name:
            update_data["full_name"] = full_name
            need_update = True

        if not user.is_active:
            update_data["is_active"] = True
            need_update = True

        if language and user.language != language:
            update_data["language"] = language
            need_update = True

        if need_update:

            query = update(User).where(User.user_id == telegram_id).values(**update_data).returning(User)

            result = await UserDAL.db.fetchrow(query)
            return result[0]

        return user

    @staticmethod
    async def set_language(telegram_id: int, language: str) -> Optional[User]:
        """
        Set user's preferred language

        Args:
            telegram_id: User's Telegram ID
            language: Language code

        Returns:
            Updated user or None if not found
        """
        query = update(User).where(User.user_id == telegram_id).values(language=language).returning(User)

        result = await UserDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_active_users() -> List[User]:
        """
        Get all active users

        Returns:
            List of active users
        """
        query = select(User).where(User.is_active == True)
        result = await UserDAL.db.fetch(query)
        return [row[0] for row in result]

    @staticmethod
    async def get_new_users_today() -> List[User]:
        """
        Get users registered today

        Returns:
            List of new users
        """
        today = datetime.now().date()
        query = select(User).where(User.created_at >= today)
        result = await UserDAL.db.fetch(query)
        return [row[0] for row in result]

    @staticmethod
    async def mark_inactive(telegram_id: int) -> bool:
        """
        Mark user as inactive

        Args:
            telegram_id: User's Telegram ID

        Returns:
            True if user was marked inactive, False otherwise
        """
        query = update(User).where(User.user_id == telegram_id).values(is_active=False).returning(User.id)

        result = await UserDAL.db.fetchval(query)
        return result is not None

    @staticmethod
    async def count_active() -> int:
        """
        Count active users

        Returns:
            Number of active users
        """
        query = select(func.count()).select_from(User).where(User.is_active == True)
        return await UserDAL.db.fetchval(query) or 0

    @staticmethod
    async def get_by_id(user_id: int) -> Optional[User]:
        """
        Get user by database ID

        Args:
            user_id: User's database ID

        Returns:
            User or None if not found
        """
        query = select(User).where(User.id == user_id)
        result = await UserDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_all() -> List[User]:
        """
        Get all users

        Returns:
            List of all users
        """
        query = select(User)
        result = await UserDAL.db.fetch(query)
        return [row[0] for row in result]
