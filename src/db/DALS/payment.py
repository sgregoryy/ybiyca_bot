from datetime import datetime
from sqlalchemy import select, update, and_, func
from src.db.database import get_db
from src.db.models import Payment, User, TariffPlan
from typing import List, Optional, Tuple, Dict, Any


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
    async def get_pending_payments() -> List[Tuple[Payment, User, TariffPlan]]:
        """
        Получить ожидающие платежи с информацией о пользователе и тарифном плане
        
        Returns:
            Список кортежей (платеж, пользователь, тарифный план)
        """
        query = (
            select(Payment, User, TariffPlan)
            .join(User, Payment.user_id == User.id)
            .join(TariffPlan, Payment.plan_id == TariffPlan.id)
            .where(Payment.status == "pending")
            .order_by(Payment.created_at.desc())
        )
        
        result = await PaymentDAL.db.fetch(query)
        return result
    
    @staticmethod
    async def create_payment(
        user_id: int, 
        plan_id: int, 
        amount: float,
        payment_method: str = "manual",
        screenshot_file_id: Optional[str] = None,
        external_id: Optional[str] = None
    ) -> Payment:
        """
        Создать новый платеж
        
        Args:
            user_id: ID пользователя в базе данных
            plan_id: ID тарифного плана
            amount: Сумма платежа
            payment_method: Метод оплаты
            screenshot_file_id: ID файла скриншота оплаты
            external_id: Внешний ID платежа
            
        Returns:
            Созданный платеж
        """
        async with PaymentDAL.db.session() as session:
            payment = Payment(
                user_id=user_id,
                plan_id=plan_id,
                amount=amount,
                payment_method=payment_method,
                screenshot_file_id=screenshot_file_id,
                external_id=external_id,
                status="pending",
                created_at=datetime.now()
            )
            session.add(payment)
            await session.commit()
            await session.refresh(payment)
            return payment
    
    @staticmethod
    async def approve_payment(payment_id: int) -> Optional[Tuple[Payment, User, TariffPlan]]:
        """
        Подтвердить платеж
        
        Args:
            payment_id: ID платежа
            
        Returns:
            Кортеж (обновленный платеж, пользователь, тарифный план) или None если платеж не найден
        """
        # Получаем платеж с пользователем и тарифом
        query = (
            select(Payment, User, TariffPlan)
            .join(User, Payment.user_id == User.id)
            .join(TariffPlan, Payment.plan_id == TariffPlan.id)
            .where(Payment.id == payment_id)
        )
        
        result = await PaymentDAL.db.fetchrow(query)
        if not result:
            return None
        
        payment, user, plan = result
        
        # Обновляем статус платежа
        update_query = (
            update(Payment)
            .where(Payment.id == payment_id)
            .values(
                status="approved",
                processed_at=datetime.now()
            )
            .returning(Payment)
        )
        
        updated_result = await PaymentDAL.db.fetchrow(update_query)
        if not updated_result:
            return None
            
        updated_payment = updated_result[0]
        
        return (updated_payment, user, plan)
    
    @staticmethod
    async def reject_payment(
        payment_id: int, 
        reason: Optional[str] = None
    ) -> Optional[Tuple[Payment, User, TariffPlan]]:
        """
        Отклонить платеж
        
        Args:
            payment_id: ID платежа
            reason: Причина отклонения
            
        Returns:
            Кортеж (обновленный платеж, пользователь, тарифный план) или None если платеж не найден
        """
        # Получаем платеж с пользователем и тарифом
        query = (
            select(Payment, User, TariffPlan)
            .join(User, Payment.user_id == User.id)
            .join(TariffPlan, Payment.plan_id == TariffPlan.id)
            .where(Payment.id == payment_id)
        )
        
        result = await PaymentDAL.db.fetchrow(query)
        if not result:
            return None
        
        payment, user, plan = result
        
        # Обновляем статус платежа
        update_query = (
            update(Payment)
            .where(Payment.id == payment_id)
            .values(
                status="rejected",
                processed_at=datetime.now(),
                notes=reason
            )
            .returning(Payment)
        )
        
        updated_result = await PaymentDAL.db.fetchrow(update_query)
        if not updated_result:
            return None
            
        updated_payment = updated_result[0]
        
        return (updated_payment, user, plan)
    
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
    async def get_user_payments(telegram_id: int) -> List[Tuple[Payment, TariffPlan]]:
        """
        Получить платежи пользователя по Telegram ID
        
        Args:
            telegram_id: ID пользователя в Telegram
            
        Returns:
            Список кортежей (платеж, тарифный план)
        """
        query = (
            select(Payment, TariffPlan)
            .join(User, Payment.user_id == User.id)
            .join(TariffPlan, Payment.plan_id == TariffPlan.id)
            .where(User.user_id == telegram_id)
            .order_by(Payment.created_at.desc())
        )
        
        result = await PaymentDAL.db.fetch(query)
        return result
    
    @staticmethod
    async def get_revenue_stats(start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Получить статистику доходов
        
        Args:
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
            
        Returns:
            Словарь со статистикой доходов
        """
        query = select(Payment).where(Payment.status == "approved")
        
        if start_date:
            query = query.where(Payment.processed_at >= start_date)
        
        if end_date:
            query = query.where(Payment.processed_at <= end_date)
        
        result = await PaymentDAL.db.fetch(query)
        payments = [row[0] for row in result]
        
        # Считаем статистику
        total_revenue = sum(payment.amount for payment in payments)
        
        # Группируем по методам оплаты
        payment_methods = {}
        for payment in payments:
            method = payment.payment_method or "unknown"
            if method in payment_methods:
                payment_methods[method] += payment.amount
            else:
                payment_methods[method] = payment.amount
        
        # Считаем среднюю сумму платежа
        avg_payment = total_revenue / len(payments) if payments else 0
        
        return {
            "total_revenue": total_revenue,
            "payment_count": len(payments),
            "payment_methods": payment_methods,
            "average_payment": avg_payment
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