"""
Data Access Layer для работы с ценами тарифов в разных валютах.
"""

from sqlalchemy import select, update, and_, func
from src.db.database import get_db
from src.db.models import TariffPrice, Currency, TariffPlan
from typing import List, Optional, Tuple, Dict


class TariffPriceDAL:
    """DAL для работы с ценами тарифов в разных валютах"""

    db = get_db()

    @staticmethod
    async def get_price(tariff_id: int, currency_id: int) -> Optional[TariffPrice]:
        """
        Получить цену тарифа в конкретной валюте

        Args:
            tariff_id: ID тарифного плана
            currency_id: ID валюты

        Returns:
            TariffPrice или None если не найдено
        """
        query = select(TariffPrice).where(
            and_(
                TariffPrice.tariff_id == tariff_id,
                TariffPrice.currency_id == currency_id,
                TariffPrice.is_active == True,
            )
        )
        result = await TariffPriceDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_price_by_code(tariff_id: int, currency_code: str) -> Optional[Tuple[TariffPrice, Currency]]:
        """
        Получить цену тарифа по коду валюты

        Args:
            tariff_id: ID тарифного плана
            currency_code: Код валюты (например, 'RUB', 'USD', 'STARS')

        Returns:
            Кортеж (TariffPrice, Currency) или None если не найдено
        """
        query = (
            select(TariffPrice, Currency)
            .join(Currency, TariffPrice.currency_id == Currency.id)
            .where(
                and_(
                    TariffPrice.tariff_id == tariff_id,
                    Currency.code == currency_code,
                    TariffPrice.is_active == True,
                    Currency.is_active == True,
                )
            )
        )
        result = await TariffPriceDAL.db.fetchrow(query)
        return result if result else None

    @staticmethod
    async def get_all_prices(tariff_id: int) -> List[Tuple[TariffPrice, Currency]]:
        """
        Получить все цены тарифа в разных валютах

        Args:
            tariff_id: ID тарифного плана

        Returns:
            Список кортежей (TariffPrice, Currency)
        """
        query = (
            select(TariffPrice, Currency)
            .join(Currency, TariffPrice.currency_id == Currency.id)
            .where(and_(TariffPrice.tariff_id == tariff_id, TariffPrice.is_active == True, Currency.is_active == True))
        )
        result = await TariffPriceDAL.db.fetch(query)
        return result

    @staticmethod
    async def set_price(tariff_id: int, currency_id: int, price: float) -> TariffPrice:
        """
        Установить или обновить цену тарифа в валюте

        Args:
            tariff_id: ID тарифного плана
            currency_id: ID валюты
            price: Цена в указанной валюте

        Returns:
            Созданная или обновленная запись о цене
        """

        existing = await TariffPriceDAL.get_price(tariff_id, currency_id)

        if existing:

            query = (
                update(TariffPrice)
                .where(TariffPrice.id == existing.id)
                .values(price=price, is_active=True)
                .returning(TariffPrice)
            )
            result = await TariffPriceDAL.db.fetchrow(query)
            return result[0]
        else:

            async with TariffPriceDAL.db.session() as session:
                price_obj = TariffPrice(tariff_id=tariff_id, currency_id=currency_id, price=price, is_active=True)
                session.add(price_obj)
                await session.commit()
                await session.refresh(price_obj)
                return price_obj

    @staticmethod
    async def init_default_prices_for_tariff(tariff_id: int, base_price: float) -> List[TariffPrice]:
        """
        Инициализировать цены для тарифа во всех валютах на основе базовой цены в рублях

        Args:
            tariff_id: ID тарифа
            base_price: Базовая цена в рублях

        Returns:
            Список созданных цен
        """

        exchange_rates = {
            "RUB": 1.0,
            "USD": 0.011,
            "STARS": 10.0,
            "BTC": 0.00000004,
            "TON": 0.004,
            "USDT": 0.011,
        }

        from src.db.DALS.currency import CurrencyDAL

        currencies = await CurrencyDAL.get_all_active()

        results = []
        for currency in currencies:
            if currency.code in exchange_rates:
                rate = exchange_rates[currency.code]

                price_in_currency = base_price * rate

                if currency.code in ["RUB", "USD", "USDT"]:
                    price_in_currency = round(price_in_currency, 2)

                elif currency.code == "STARS":
                    price_in_currency = round(price_in_currency)

                else:
                    price_in_currency = round(price_in_currency, 8)

                price = await TariffPriceDAL.set_price(
                    tariff_id=tariff_id, currency_id=currency.id, price=price_in_currency
                )

                results.append(price)

        return results

    @staticmethod
    async def delete_price(tariff_id: int, currency_id: int) -> bool:
        """
        Деактивировать цену для тарифа в указанной валюте

        Args:
            tariff_id: ID тарифного плана
            currency_id: ID валюты

        Returns:
            True если цена успешно деактивирована, False в противном случае
        """
        query = (
            update(TariffPrice)
            .where(and_(TariffPrice.tariff_id == tariff_id, TariffPrice.currency_id == currency_id))
            .values(is_active=False)
            .returning(TariffPrice.id)
        )

        result = await TariffPriceDAL.db.fetchval(query)
        return result is not None
