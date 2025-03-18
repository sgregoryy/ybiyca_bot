import logging
from typing import Any, Optional, Sequence, Dict, TypeVar, Type
from sqlalchemy import select, Row
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from src.config import config

Base = declarative_base()


logger = logging.getLogger(__name__)


URL_DATABASE = config.db.url


class Database:
    """
    Класс для работы с базой данных через SQLAlchemy.
    """
    
    _engine: AsyncEngine
    session: async_sessionmaker[AsyncSession]
    _database_url: str

    def __init__(self, base_url: str = None):
        """Инициализация соединения с базой данных."""
        if not base_url:
            base_url = URL_DATABASE
            
        self._database_url = base_url
        

        engine = create_async_engine(
            base_url,
            echo=config.debug,
            future=True,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        
        self._engine = engine
        

        self.session = async_sessionmaker(engine, expire_on_commit=False)

    def __await__(self):
        """Создание таблиц при инициализации"""
        return self._reset_all_tables().__await__()

    async def _reset_all_tables(self):
        """Создание всех таблиц, описанных в моделях"""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return self

    async def fetchval(self, query: Any) -> Any | None:
        """Получить одно значение из первой строки результата запроса."""
        async with self.session() as session:
            res = await session.execute(query)
            try:
                return res.scalar()
            except (TypeError, IndexError):
                return None

    async def fetchrow(self, query: Any) -> Row[Any] | None:
        """Получить первую строку результата запроса."""
        async with self.session() as session:
            res = await session.execute(query)
            return res.first()

    async def fetch(self, query: Any) -> Sequence[Row[Any]]:
        """Получить все строки результата запроса."""
        async with self.session() as session:
            res = await session.execute(query)
            return res.all()

    async def execute(self, query: Any, **kwargs):
        """Выполнить запрос и зафиксировать изменения."""
        async with self.session() as session:
            result = await session.execute(query, **kwargs)
            await session.commit()
            return result


_db_instance = None

def get_db(url: str = None) -> Database:
    """Получить экземпляр базы данных."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(base_url=url)
    return _db_instance


async def init_db() -> Database:
    """Инициализировать базу данных и создать таблицы."""
    db = get_db()
    await db._reset_all_tables()
    return db


async def close_db_connection():
    """Закрыть соединение с базой данных."""
    global _db_instance
    if _db_instance is not None:
        await _db_instance._engine.dispose()
        _db_instance = None
        logger.info("Database connection closed")