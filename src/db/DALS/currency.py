from sqlalchemy import select, update, and_
from src.db.database import get_db
from src.db.models import Currency
from typing import List, Optional


class CurrencyDAL:
    """DAL для работы с валютами"""

    db = get_db()

    @staticmethod
    async def get_by_id(currency_id: int) -> Optional[Currency]:
        """
        Получить валюту по ID

        Args:
            currency_id: ID валюты

        Returns:
            Currency или None если не найдено
        """
        query = select(Currency).where(Currency.id == currency_id)
        result = await CurrencyDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_by_code(code: str) -> Optional[Currency]:
        """
        Получить валюту по коду

        Args:
            code: Код валюты (например, 'RUB', 'USD', 'STARS')

        Returns:
            Currency или None если не найдено
        """
        query = select(Currency).where(Currency.code == code)
        result = await CurrencyDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_all_active() -> List[Currency]:
        """
        Получить все активные валюты

        Returns:
            Список активных валют
        """
        query = select(Currency).where(Currency.is_active == True).order_by(Currency.code)
        result = await CurrencyDAL.db.fetch(query)
        return [row[0] for row in result]

    @staticmethod
    async def create_currency(
        code: str, name: str, symbol: str, requires_manual_confirmation: bool = False
    ) -> Currency:
        """
        Создать новую валюту

        Args:
            code: Код валюты (например, 'RUB', 'USD', 'BTC')
            name: Название валюты
            symbol: Символ валюты
            requires_manual_confirmation: Требуется ли ручное подтверждение платежей

        Returns:
            Созданная валюта
        """

        existing = await CurrencyDAL.get_by_code(code)
        if existing:
            return existing

        async with CurrencyDAL.db.session() as session:
            currency = Currency(
                code=code,
                name=name,
                symbol=symbol,
                is_active=True,
                requires_manual_confirmation=requires_manual_confirmation,
            )
            session.add(currency)
            await session.commit()
            await session.refresh(currency)
            return currency

    @staticmethod
    async def toggle_active(currency_id: int) -> Optional[Currency]:
        """
        Переключить активность валюты

        Args:
            currency_id: ID валюты

        Returns:
            Обновленная валюта или None если не найдено
        """

        currency = await CurrencyDAL.get_by_id(currency_id)
        if not currency:
            return None

        new_state = not currency.is_active

        query = update(Currency).where(Currency.id == currency_id).values(is_active=new_state).returning(Currency)

        result = await CurrencyDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def update_currency(currency_id: int, **kwargs) -> Optional[Currency]:
        """
        Обновить валюту

        Args:
            currency_id: ID валюты
            **kwargs: Параметры для обновления

        Returns:
            Обновленная валюта или None если не найдено
        """
        query = update(Currency).where(Currency.id == currency_id).values(**kwargs).returning(Currency)

        result = await CurrencyDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def initialize_default_currencies() -> List[Currency]:
        """
        Инициализировать валюты по умолчанию

        Returns:
            Список созданных или обновленных валют
        """
        default_currencies = [
            {"code": "RUB", "name": "Российский рубль", "symbol": "₽", "requires_manual_confirmation": True},
            {"code": "USD", "name": "Доллар США", "symbol": "$", "requires_manual_confirmation": True},
            {"code": "STARS", "name": "Telegram Stars", "symbol": "⭐", "requires_manual_confirmation": False},
            {"code": "BTC", "name": "Bitcoin", "symbol": "₿", "requires_manual_confirmation": False},
            {"code": "TON", "name": "Toncoin", "symbol": "💎", "requires_manual_confirmation": False},
            {"code": "USDT", "name": "Tether", "symbol": "₮", "requires_manual_confirmation": False},
        ]

        result = []

        for currency_data in default_currencies:
            currency = await CurrencyDAL.create_currency(
                code=currency_data["code"],
                name=currency_data["name"],
                symbol=currency_data["symbol"],
                requires_manual_confirmation=currency_data["requires_manual_confirmation"],
            )
            result.append(currency)

        return result
