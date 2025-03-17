"""
Data Access Layer для работы с тарифными планами.
"""

from sqlalchemy import select, update, and_, desc, func
from src.db.database import get_db
from src.db.models import TariffPlan
from typing import List, Optional, Dict, Any


class TariffDAL:
    """DAL для работы с тарифными планами"""
    db = get_db()
    
    @staticmethod
    async def get_by_id(tariff_id: int) -> Optional[TariffPlan]:
        """
        Получить тарифный план по ID
        
        Args:
            tariff_id: ID тарифного плана
            
        Returns:
            Тарифный план или None если не найден
        """
        query = select(TariffPlan).where(TariffPlan.id == tariff_id)
        result = await TariffDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def get_by_code(code: str) -> Optional[TariffPlan]:
        """
        Получить тарифный план по коду
        
        Args:
            code: Код тарифного плана
            
        Returns:
            Тарифный план или None если не найден
        """
        query = select(TariffPlan).where(TariffPlan.code == code)
        result = await TariffDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def get_active_plans() -> List[TariffPlan]:
        """
        Получить все активные тарифные планы
        
        Returns:
            Список активных тарифных планов
        """
        query = (
            select(TariffPlan)
            .where(TariffPlan.is_active == True)
            .order_by(TariffPlan.display_order)
        )
        
        result = await TariffDAL.db.fetch(query)
        return [row[0] for row in result]
    
    @staticmethod
    async def toggle_active(tariff_id: int) -> Optional[TariffPlan]:
        """
        Переключить статус активности тарифного плана
        
        Args:
            tariff_id: ID тарифного плана
            
        Returns:
            Обновленный тарифный план или None если не найден
        """
        # Получаем текущее состояние
        tariff = await TariffDAL.get_by_id(tariff_id)
        if not tariff:
            return None
            
        new_state = not tariff.is_active
        
        # Обновляем состояние
        query = (
            update(TariffPlan)
            .where(TariffPlan.id == tariff_id)
            .values(is_active=new_state)
            .returning(TariffPlan)
        )
        
        result = await TariffDAL.db.fetchrow(query)
        return result[0] if result else None
    
    @staticmethod
    async def initialize_default_plans(default_plans: List[Dict[str, Any]]) -> List[TariffPlan]:
        """
        Инициализировать стандартные тарифные планы
        
        Args:
            default_plans: Список конфигураций тарифных планов по умолчанию
            
        Returns:
            Список тарифных планов
        """
        result = []
        
        for plan_data in default_plans:
            # Проверяем, существует ли план с таким кодом
            plan = await TariffDAL.get_by_code(plan_data["code"])
            
            if plan is None:
                # Создаем новый тарифный план
                async with TariffDAL.db.session() as session:
                    plan = TariffPlan(**plan_data)
                    session.add(plan)
                    await session.commit()
                    await session.refresh(plan)
            else:
                # Проверяем, нужно ли обновить данные
                need_update = False
                update_data = {}
                
                for key, value in plan_data.items():
                    if hasattr(plan, key) and getattr(plan, key) != value:
                        update_data[key] = value
                        need_update = True
                
                if need_update:
                    # Обновляем данные плана
                    query = (
                        update(TariffPlan)
                        .where(TariffPlan.id == plan.id)
                        .values(**update_data)
                        .returning(TariffPlan)
                    )
                    
                    result_row = await TariffDAL.db.fetchrow(query)
                    plan = result_row[0]
            
            result.append(plan)
        
        return result
    
    @staticmethod
    async def get_max_display_order() -> int:
        """
        Получить максимальный порядок отображения
        
        Returns:
            Максимальный порядок отображения
        """
        query = select(func.max(TariffPlan.display_order))
        return await TariffDAL.db.fetchval(query) or 0
    
    @staticmethod
    async def create_tariff(
        name: str, 
        code: str, 
        price: float, 
        duration_days: int
    ) -> TariffPlan:
        """
        Создать новый тарифный план
        
        Args:
            name: Название тарифного плана
            code: Код тарифного плана
            price: Стоимость тарифного плана
            duration_days: Длительность тарифного плана в днях
            
        Returns:
            Созданный тарифный план
        """
        # Получаем максимальный порядок отображения
        max_order = await TariffDAL.get_max_display_order()
        
        # Создаем новый тарифный план
        async with TariffDAL.db.session() as session:
            plan = TariffPlan(
                name=name,
                code=code,
                price=price,
                duration_days=duration_days,
                is_active=True,
                display_order=max_order + 1
            )
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            return plan
    
    @staticmethod
    async def get_all_plans() -> List[TariffPlan]:
        """
        Получить все тарифные планы
        
        Returns:
            Список всех тарифных планов
        """
        query = select(TariffPlan).order_by(TariffPlan.display_order)
        result = await TariffDAL.db.fetch(query)
        return [row[0] for row in result]