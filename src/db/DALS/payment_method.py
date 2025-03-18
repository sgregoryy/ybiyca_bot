"""
Data Access Layer для работы с методами оплаты и поддерживаемыми валютами.
"""

import json
from sqlalchemy import select, update, delete, and_, desc, func
from src.db.database import get_db
from src.db.models import PaymentMethod, PaymentMethodCurrency, Currency
from typing import List, Optional, Dict, Any, Tuple


class PaymentMethodDAL:
    """DAL для работы с методами оплаты"""
    db = get_db()
    
    @staticmethod
    async def get_by_id(method_id: int) -> Optional[PaymentMethod]:
        """
        Получить метод оплаты по ID
        
        Args:
            method_id: ID метода оплаты
            
        Returns:
            Метод оплаты или None если не найден
        """
        query = select(PaymentMethod).where(PaymentMethod.id == method_id)
        result = await PaymentMethodDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def get_by_code(code: str) -> Optional[PaymentMethod]:
        """
        Получить метод оплаты по коду
        
        Args:
            code: Код метода оплаты
            
        Returns:
            Метод оплаты или None если не найден
        """
        query = select(PaymentMethod).where(PaymentMethod.code == code)
        result = await PaymentMethodDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def get_active_methods() -> List[PaymentMethod]:
        """
        Получить все активные методы оплаты
        
        Returns:
            Список активных методов оплаты
        """
        query = (
            select(PaymentMethod)
            .where(PaymentMethod.is_active == True)
            .order_by(PaymentMethod.display_order)
        )
        
        result = await PaymentMethodDAL.db.fetch(query)
        return [row[0] for row in result]
    
    @staticmethod
    async def get_supported_currencies(method_id: int) -> List[Tuple[PaymentMethodCurrency, Currency]]:
        """
        Получить поддерживаемые валюты для метода оплаты
        
        Args:
            method_id: ID метода оплаты
            
        Returns:
            Список кортежей (PaymentMethodCurrency, Currency)
        """
        query = (
            select(PaymentMethodCurrency, Currency)
            .join(Currency, PaymentMethodCurrency.currency_id == Currency.id)
            .where(and_(
                PaymentMethodCurrency.payment_method_id == method_id,
                Currency.is_active == True
            ))
            .order_by(PaymentMethodCurrency.is_default.desc())
        )
        
        result = await PaymentMethodDAL.db.fetch(query)
        return result
    
    @staticmethod
    async def get_default_currency(method_id: int) -> Optional[Currency]:
        """
        Получить валюту по умолчанию для метода оплаты
        
        Args:
            method_id: ID метода оплаты
            
        Returns:
            Валюта по умолчанию или None если не найдена
        """
        query = (
            select(Currency)
            .join(PaymentMethod, PaymentMethod.default_currency_id == Currency.id)
            .where(PaymentMethod.id == method_id)
        )
        
        result = await PaymentMethodDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def toggle_active(method_id: int) -> Optional[PaymentMethod]:
        """
        Переключить статус активности метода оплаты
        
        Args:
            method_id: ID метода оплаты
            
        Returns:
            Обновленный метод оплаты или None если не найден
        """
        # Получаем текущее состояние
        method = await PaymentMethodDAL.get_by_id(method_id)
        if not method:
            return None
            
        new_state = not method.is_active
        
        # Обновляем состояние
        query = (
            update(PaymentMethod)
            .where(PaymentMethod.id == method_id)
            .values(is_active=new_state)
            .returning(PaymentMethod)
        )
        
        result = await PaymentMethodDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def initialize_default_methods() -> List[PaymentMethod]:
        """
        Инициализировать методы оплаты по умолчанию
        
        Returns:
            Список созданных или обновленных методов оплаты
        """
        from src.db.DALS.currency import CurrencyDAL
        
        # Получаем валюты
        rub = await CurrencyDAL.get_by_code("RUB")
        usd = await CurrencyDAL.get_by_code("USD")
        ton = await CurrencyDAL.get_by_code("TON")
        stars = await CurrencyDAL.get_by_code("STARS")
        
        if not rub or not usd or not ton or not stars:
            # Инициализируем валюты, если их нет
            await CurrencyDAL.initialize_default_currencies()
            rub = await CurrencyDAL.get_by_code("RUB")
            usd = await CurrencyDAL.get_by_code("USD")
            ton = await CurrencyDAL.get_by_code("TON")
            stars = await CurrencyDAL.get_by_code("STARS")
        
        default_methods = [
            {
                "name": "Ручная оплата",
                "code": "manual",
                "default_currency_id": rub.id,
                "supported_currencies": [rub.id],
                "price_modifier": 0.0,
                "fixed_fee": 0.0,
                "settings": {},
                "is_active": True,
                "display_order": 1
            },
            {
                "name": "ЮKassa",
                "code": "youkassa",
                "default_currency_id": rub.id,
                "supported_currencies": [rub.id],
                "price_modifier": 2.8,  # 2.8% комиссия
                "fixed_fee": 0.0,
                "settings": {},
                "is_active": True,
                "display_order": 2
            },
            {
                "name": "Tinkoff",
                "code": "tinkoff",
                "default_currency_id": rub.id,
                "supported_currencies": [rub.id],
                "price_modifier": 2.5,  # 2.5% комиссия
                "fixed_fee": 0.0,
                "settings": {},
                "is_active": True,
                "display_order": 3
            },
            {
                "name": "CryptoBot",
                "code": "cryptobot",
                "default_currency_id": ton.id,
                "supported_currencies": [ton.id, usd.id],
                "price_modifier": 1.0,  # 1% комиссия
                "fixed_fee": 0.0,
                "settings": {},
                "is_active": True,
                "display_order": 4
            },
            {
                "name": "Telegram Stars",
                "code": "stars",
                "default_currency_id": stars.id,
                "supported_currencies": [stars.id],
                "price_modifier": 0.0,
                "fixed_fee": 0.0,
                "settings": {},
                "is_active": True,
                "display_order": 5
            }
        ]
        
        result = []
        
        for method_data in default_methods:
            supported_currencies = method_data.pop("supported_currencies")
            
            # Проверяем, существует ли метод с таким кодом
            method = await PaymentMethodDAL.get_by_code(method_data["code"])
            
            if method is None:
                # Создаем новый метод оплаты
                async with PaymentMethodDAL.db.session() as session:
                    # Преобразуем настройки в JSON
                    if "settings" in method_data and isinstance(method_data["settings"], dict):
                        method_data["settings"] = json.dumps(method_data["settings"])
                        
                    method = PaymentMethod(**method_data)
                    session.add(method)
                    await session.commit()
                    await session.refresh(method)
            else:
                # Проверяем, нужно ли обновить данные
                need_update = False
                update_data = {}
                
                for key, value in method_data.items():
                    if key == "settings" and isinstance(value, dict):
                        value = json.dumps(value)
                        
                    if hasattr(method, key) and getattr(method, key) != value:
                        update_data[key] = value
                        need_update = True
                
                if need_update:
                    # Обновляем данные метода
                    query = (
                        update(PaymentMethod)
                        .where(PaymentMethod.id == method.id)
                        .values(**update_data)
                        .returning(PaymentMethod)
                    )
                    
                    result_row = await PaymentMethodDAL.db.fetchrow(query)
                    method = result_row[0]
            
            # Добавляем поддерживаемые валюты
            for currency_id in supported_currencies:
                await PaymentMethodDAL.add_currency_to_method(method.id, currency_id, 
                                                           is_default=(currency_id == method_data["default_currency_id"]))
            
            result.append(method)
        
        return result
    
    @staticmethod
    async def add_currency_to_method(method_id: int, currency_id: int, is_default: bool = False) -> Optional[PaymentMethodCurrency]:
        """
        Добавить валюту к методу оплаты
        
        Args:
            method_id: ID метода оплаты
            currency_id: ID валюты
            is_default: Является ли валютой по умолчанию
            
        Returns:
            Созданная связь или None в случае ошибки
        """
        # Проверяем, существует ли уже такая связь
        query = (
            select(PaymentMethodCurrency)
            .where(and_(
                PaymentMethodCurrency.payment_method_id == method_id,
                PaymentMethodCurrency.currency_id == currency_id
            ))
        )
        
        existing = await PaymentMethodDAL.db.fetchrow(query)
        if existing:
            # Если связь уже существует, обновляем флаг is_default
            existing_rel = existing[0]
            if existing_rel.is_default != is_default:
                update_query = (
                    update(PaymentMethodCurrency)
                    .where(PaymentMethodCurrency.id == existing_rel.id)
                    .values(is_default=is_default)
                    .returning(PaymentMethodCurrency)
                )
                
                result = await PaymentMethodDAL.db.fetchrow(update_query)
                return result[0] if result else existing_rel
            
            return existing_rel
        
        # Создаем новую связь
        async with PaymentMethodDAL.db.session() as session:
            method_currency = PaymentMethodCurrency(
                payment_method_id=method_id,
                currency_id=currency_id,
                is_default=is_default
            )
            session.add(method_currency)
            await session.commit()
            await session.refresh(method_currency)
            return method_currency
    
    @staticmethod
    async def remove_currency_from_method(method_id: int, currency_id: int) -> bool:
        """
        Удалить валюту из метода оплаты
        
        Args:
            method_id: ID метода оплаты
            currency_id: ID валюты
            
        Returns:
            True если связь удалена, False в противном случае
        """
        query = delete(PaymentMethodCurrency).where(
            and_(
                PaymentMethodCurrency.payment_method_id == method_id,
                PaymentMethodCurrency.currency_id == currency_id
            )
        ).returning(PaymentMethodCurrency.id)
        
        result = await PaymentMethodDAL.db.fetchval(query)
        return result is not None
    
    @staticmethod
    async def get_max_display_order() -> int:
        """
        Получить максимальный порядок отображения
        
        Returns:
            Максимальный порядок отображения
        """
        query = select(func.max(PaymentMethod.display_order))
        return await PaymentMethodDAL.db.fetchval(query) or 0
    
    @staticmethod
    async def create_method(
        name: str, 
        code: str, 
        default_currency_id: int,
        price_modifier: float = 0.0, 
        fixed_fee: float = 0.0,
        settings: Dict[str, Any] = None,
        supported_currency_ids: List[int] = None
    ) -> PaymentMethod:
        """
        Создать новый метод оплаты
        
        Args:
            name: Название метода оплаты
            code: Код метода оплаты
            default_currency_id: ID валюты по умолчанию
            price_modifier: Модификатор цены в процентах
            fixed_fee: Фиксированная комиссия
            settings: Дополнительные настройки
            supported_currency_ids: Список ID поддерживаемых валют
            
        Returns:
            Созданный метод оплаты
        """
        # Получаем максимальный порядок отображения
        max_order = await PaymentMethodDAL.get_max_display_order()
        
        # Преобразуем настройки в JSON
        settings_json = json.dumps(settings) if settings else None
        
        # Создаем новый метод оплаты
        async with PaymentMethodDAL.db.session() as session:
            method = PaymentMethod(
                name=name,
                code=code,
                default_currency_id=default_currency_id,
                price_modifier=price_modifier,
                fixed_fee=fixed_fee,
                settings=settings_json,
                is_active=True,
                display_order=max_order + 1
            )
            session.add(method)
            await session.commit()
            await session.refresh(method)
            
            # Добавляем поддерживаемые валюты
            if supported_currency_ids:
                for currency_id in supported_currency_ids:
                    await PaymentMethodDAL.add_currency_to_method(
                        method.id, 
                        currency_id, 
                        is_default=(currency_id == default_currency_id)
                    )
            else:
                # Если список валют не указан, добавляем только валюту по умолчанию
                await PaymentMethodDAL.add_currency_to_method(
                    method.id, 
                    default_currency_id, 
                    is_default=True
                )
                
            return method
    
    @staticmethod
    async def update_method(
        method_id: int,
        **kwargs
    ) -> Optional[PaymentMethod]:
        """
        Обновить метод оплаты
        
        Args:
            method_id: ID метода оплаты
            kwargs: Параметры для обновления
            
        Returns:
            Обновленный метод оплаты или None если не найден
        """
        # Если есть настройки, преобразуем их в JSON
        if 'settings' in kwargs and isinstance(kwargs['settings'], dict):
            kwargs['settings'] = json.dumps(kwargs['settings'])
        
        # Обрабатываем supported_currency_ids отдельно
        supported_currency_ids = kwargs.pop('supported_currency_ids', None)
        
        # Обновляем метод оплаты
        query = (
            update(PaymentMethod)
            .where(PaymentMethod.id == method_id)
            .values(**kwargs)
            .returning(PaymentMethod)
        )
        
        result = await PaymentMethodDAL.db.fetchrow(query)
        if not result:
            return None
            
        updated_method = result[0]
        
        # Обновляем поддерживаемые валюты, если указаны
        if supported_currency_ids is not None:
            # Удаляем все текущие связи
            delete_query = delete(PaymentMethodCurrency).where(
                PaymentMethodCurrency.payment_method_id == method_id
            )
            await PaymentMethodDAL.db.execute(delete_query)
            
            # Добавляем новые связи
            for currency_id in supported_currency_ids:
                await PaymentMethodDAL.add_currency_to_method(
                    method_id, 
                    currency_id, 
                    is_default=(currency_id == updated_method.default_currency_id)
                )
        
        return updated_method
    
    @staticmethod
    async def get_all_methods() -> List[PaymentMethod]:
        """
        Получить все методы оплаты
        
        Returns:
            Список всех методов оплаты
        """
        query = select(PaymentMethod).order_by(PaymentMethod.display_order)
        result = await PaymentMethodDAL.db.fetch(query)
        return [row[0] for row in result]
    
    @staticmethod
    async def delete_method(method_id: int) -> bool:
        """
        Удалить метод оплаты
        
        Args:
            method_id: ID метода оплаты
            
        Returns:
            True если метод удален, False в противном случае
        """
        # Сначала удаляем связи с валютами
        delete_currencies_query = delete(PaymentMethodCurrency).where(
            PaymentMethodCurrency.payment_method_id == method_id
        )
        await PaymentMethodDAL.db.execute(delete_currencies_query)
        
        # Теперь удаляем сам метод
        query = delete(PaymentMethod).where(PaymentMethod.id == method_id).returning(PaymentMethod.id)
        result = await PaymentMethodDAL.db.fetchval(query)
        return result is not None
    
    @staticmethod
    async def calculate_price_with_method(base_price: float, method_id: int) -> float:
        """
        Рассчитать итоговую цену с учетом метода оплаты
        
        Args:
            base_price: Базовая цена
            method_id: ID метода оплаты
            
        Returns:
            Итоговая цена
        """
        # Получаем метод оплаты
        method = await PaymentMethodDAL.get_by_id(method_id)
        
        if not method:
            return base_price
        
        # Применяем модификатор цены и фиксированную комиссию
        modified_price = base_price * (1 + method.price_modifier / 100) + method.fixed_fee
        
        # Округляем до 2 знаков после запятой
        return round(modified_price, 2)