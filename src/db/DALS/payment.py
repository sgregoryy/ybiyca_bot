"""
Data Access Layer для работы с платежами с поддержкой разных валют и способов оплаты
"""

from datetime import datetime
from sqlalchemy import select, update, and_, func
from src.db.database import get_db
from src.db.models import Payment, User, TariffPlan, Currency, PaymentMethod
from typing import List, Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)

class PaymentDAL:
    """DAL для работы с платежами"""

    db = get_db()

    @staticmethod
    async def get_by_id(payment_id: int) -> Optional[Payment]:
        """
        Получить платеж по ID

        Args:
            payment_id: ID платежа

        Returns:
            Платеж или None если не найден
        """
        query = select(Payment).where(Payment.id == payment_id)
        result = await PaymentDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_payment_with_details(
        payment_id: int,
    ) -> Optional[Tuple[Payment, User, TariffPlan, Currency, PaymentMethod]]:
        """
        Получить платеж с информацией о пользователе, тарифном плане, валюте и способе оплаты

        Args:
            payment_id: ID платежа

        Returns:
            Кортеж (платеж, пользователь, тарифный план, валюта, способ оплаты) или None если не найден
        """
        query = (
            select(Payment, User, TariffPlan, Currency, PaymentMethod)
            .join(User, Payment.user_id == User.id)
            .join(TariffPlan, Payment.plan_id == TariffPlan.id)
            .join(Currency, Payment.currency_id == Currency.id)
            .join(PaymentMethod, Payment.payment_method_id == PaymentMethod.id)
            .where(Payment.id == payment_id)
        )

        result = await PaymentDAL.db.fetchrow(query)
        return result if result else None

    @staticmethod
    async def get_pending_payments() -> List[Tuple[Payment, User, TariffPlan, Currency, PaymentMethod]]:
        """
        Получить ожидающие платежи с информацией о пользователе, тарифном плане, валюте и способе оплаты

        Returns:
            Список кортежей (платеж, пользователь, тарифный план, валюта, способ оплаты)
        """
        query = (
            select(Payment, User, TariffPlan, Currency, PaymentMethod)
            .join(User, Payment.user_id == User.id)
            .join(TariffPlan, Payment.plan_id == TariffPlan.id)
            .join(Currency, Payment.currency_id == Currency.id)
            .join(PaymentMethod, Payment.payment_method_id == PaymentMethod.id)
            .where(Payment.status == "pending")
            .order_by(Payment.created_at.desc())
        )

        result = await PaymentDAL.db.fetch(query)
        return result

    @staticmethod
    async def get_pending_payments_by_user_and_method(
        user_id: int, payment_method_id: int, currency_id: Optional[int] = None
    ) -> List[Tuple[Payment, TariffPlan, Currency, PaymentMethod]]:
        """
        Получить ожидающие платежи пользователя по способу оплаты и валюте

        Args:
            user_id: ID пользователя
            payment_method_id: ID способа оплаты
            currency_id: ID валюты (опционально)

        Returns:
            Список кортежей (платеж, тарифный план, валюта, способ оплаты)
        """
        filters = [
            Payment.user_id == user_id,
            Payment.payment_method_id == payment_method_id,
            Payment.status == "pending",
        ]

        if currency_id is not None:
            filters.append(Payment.currency_id == currency_id)

        query = (
            select(Payment, TariffPlan, Currency, PaymentMethod)
            .join(TariffPlan, Payment.plan_id == TariffPlan.id)
            .join(Currency, Payment.currency_id == Currency.id)
            .join(PaymentMethod, Payment.payment_method_id == PaymentMethod.id)
            .where(and_(*filters))
            .order_by(Payment.created_at.desc())
        )

        result = await PaymentDAL.db.fetch(query)
        return result

    @staticmethod
    async def create_payment(
        user_id: int,
        plan_id: int,
        payment_method_id: int,
        currency_id: int,
        amount: float,
        screenshot_file_id: Optional[str] = None,
        external_id: Optional[str] = None,
        status: str = "pending",
    ) -> Payment:
        """
        Создать новый платеж

        Args:
            user_id: ID пользователя в базе данных
            plan_id: ID тарифного плана
            payment_method_id: ID способа оплаты
            currency_id: ID валюты
            amount: Сумма платежа
            screenshot_file_id: ID файла скриншота оплаты
            external_id: Внешний ID платежа
            status: Статус платежа (по умолчанию "pending")

        Returns:
            Созданный платеж
        """
        async with PaymentDAL.db.session() as session:
            payment = Payment(
                user_id=user_id,
                plan_id=plan_id,
                payment_method_id=payment_method_id,
                currency_id=currency_id,
                amount=amount,
                screenshot_file_id=screenshot_file_id,
                external_id=external_id,
                status=status,
                created_at=datetime.now(),
            )
            session.add(payment)
            await session.commit()
            await session.refresh(payment)
            return payment

    @staticmethod
    async def update_payment(payment_id: int, **kwargs) -> Optional[Payment]:
        """
        Обновить платеж

        Args:
            payment_id: ID платежа
            **kwargs: Параметры для обновления

        Returns:
            Обновленный платеж или None если не найден
        """
        query = update(Payment).where(Payment.id == payment_id).values(**kwargs).returning(Payment)

        result = await PaymentDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def approve_payment(payment_id: int) -> Optional[Tuple[Payment, User, TariffPlan, Currency, PaymentMethod]]:
        """
        Подтвердить платеж

        Args:
            payment_id: ID платежа

        Returns:
            Кортеж (обновленный платеж, пользователь, тарифный план, валюта, способ оплаты) или None если платеж не найден
        """

        result = await PaymentDAL.get_payment_with_details(payment_id)
        if not result:
            return None

        payment, user, plan, currency, payment_method = result

        update_query = (
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="approved", processed_at=datetime.now())
            .returning(Payment)
        )

        # При использовании execute нужно по-другому получать результат
        result = await PaymentDAL.db.execute(update_query)
        updated_payment = result.scalar_one_or_none()  # Получаем один результат или None
        
        if not updated_payment:
            return None

        # Возвращаем обновленный платеж вместо первоначального
        return (updated_payment, user, plan, currency, payment_method)

    @staticmethod
    async def reject_payment(
        payment_id: int, reason: Optional[str] = None
    ) -> Optional[Tuple[Payment, User, TariffPlan, Currency, PaymentMethod]]:
        """
        Отклонить платеж

        Args:
            payment_id: ID платежа
            reason: Причина отклонения

        Returns:
            Кортеж (обновленный платеж, пользователь, тарифный план, валюта, способ оплаты) или None если платеж не найден
        """

        result = await PaymentDAL.get_payment_with_details(payment_id)
        if not result:
            return None

        payment, user, plan, currency, payment_method = result

        update_query = (
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="rejected", processed_at=datetime.now(), notes=reason)
            .returning(Payment)
        )

        updated_result = await PaymentDAL.db.fetchrow(update_query)
        if not updated_result:
            return None

        updated_payment = updated_result[0]

        return (updated_payment, user, plan, currency, payment_method)

    @staticmethod
    async def cancel_payment(payment_id: int) -> bool:
        """
        Отменить платеж

        Args:
            payment_id: ID платежа

        Returns:
            True если платеж успешно отменен, False в противном случае
        """
        query = (
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="cancelled", processed_at=datetime.now())
            .returning(Payment.id)
        )

        result = await PaymentDAL.db.fetchval(query)
        return result is not None

    @staticmethod
    async def get_by_external_id(external_id: str) -> Optional[Payment]:
        """
        Получить платеж по внешнему ID

        Args:
            external_id: Внешний ID платежа

        Returns:
            Платеж или None если не найден
        """
        query = select(Payment).where(Payment.external_id == external_id)
        result = await PaymentDAL.db.fetchrow(query)
        return result[0] if result else None

    @staticmethod
    async def get_user_payments(telegram_id: int) -> List[Tuple[Payment, TariffPlan, Currency, PaymentMethod]]:
        """
        Получить платежи пользователя по Telegram ID

        Args:
            telegram_id: ID пользователя в Telegram

        Returns:
            Список кортежей (платеж, тарифный план, валюта, способ оплаты)
        """
        query = (
            select(Payment, TariffPlan, Currency, PaymentMethod)
            .join(User, Payment.user_id == User.id)
            .join(TariffPlan, Payment.plan_id == TariffPlan.id)
            .join(Currency, Payment.currency_id == Currency.id)
            .join(PaymentMethod, Payment.payment_method_id == PaymentMethod.id)
            .where(User.user_id == telegram_id)
            .order_by(Payment.created_at.desc())
        )

        result = await PaymentDAL.db.fetch(query)
        return result

    @staticmethod
    async def get_revenue_stats() -> Dict[str, Any]:
        """
        Получить статистику доходов

        Returns:
            Словарь со статистикой доходов
        """
        query = select(Payment).where(Payment.status == "approved")

        result = await PaymentDAL.db.fetch(query)
        payments = [row[0] for row in result]

        currency_stats = {}
        for payment in payments:
            currency_id = payment.currency_id
            if currency_id in currency_stats:
                currency_stats[currency_id] += payment.amount
            else:
                currency_stats[currency_id] = payment.amount

        currency_codes = {}
        for currency_id in currency_stats.keys():
            query = select(Currency.code).where(Currency.id == currency_id)
            code = await PaymentDAL.db.fetchval(query)
            if code:
                currency_codes[currency_id] = code

        formatted_stats = {}
        for currency_id, amount in currency_stats.items():
            currency_code = currency_codes.get(currency_id, f"Unknown ({currency_id})")
            formatted_stats[currency_code] = amount

        rub_total = formatted_stats.get("RUB", 0)

        payment_count = len(payments)

        avg_payment_rub = rub_total / payment_count if payment_count and rub_total else 0

        payment_methods = {}
        for payment in payments:

            method_query = select(PaymentMethod.code).where(PaymentMethod.id == payment.payment_method_id)
            method_code = await PaymentDAL.db.fetchval(method_query) or "unknown"

            if method_code in payment_methods:
                payment_methods[method_code] += 1
            else:
                payment_methods[method_code] = 1

        return {
            "total_by_currency": formatted_stats,
            "total_rub": rub_total,
            "payment_count": payment_count,
            "payment_methods": payment_methods,
            "average_payment_rub": avg_payment_rub,
        }

    @staticmethod
    async def count_pending() -> int:
        """
        Подсчитать количество ожидающих платежей

        Returns:
            Количество ожидающих платежей
        """
        query = select(func.count()).select_from(Payment).where(Payment.status == "pending")
        return await PaymentDAL.db.fetchval(query) or 0

    @staticmethod
    async def count_approved() -> int:
        """
        Подсчитать количество подтвержденных платежей

        Returns:
            Количество подтвержденных платежей
        """
        query = select(func.count()).select_from(Payment).where(Payment.status == "approved")
        return await PaymentDAL.db.fetchval(query) or 0
