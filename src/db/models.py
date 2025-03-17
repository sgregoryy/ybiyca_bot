from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.db.database import Base
import enum

class SubscriptionPlan(enum.Enum):
    MONTH_1 = "1_month"
    MONTH_3 = "3_months"
    MONTH_6 = "6_months"
    YEAR_1 = "1_year"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="user")

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("tariff_plans.id"), nullable=False)
    start_date = Column(DateTime, server_default=func.now())
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("TariffPlan")

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("tariff_plans.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    screenshot_file_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User")
    plan = relationship("TariffPlan")

class TariffPlan(Base):
    __tablename__ = "tariff_plans"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Название тарифа (например, "1 месяц")
    code = Column(String, nullable=False, unique=True)  # Код тарифа (например, "1_month")
    price = Column(Integer, nullable=False)  # Цена в рублях
    duration_days = Column(Integer, nullable=False)  # Длительность подписки в днях
    is_active = Column(Boolean, default=True)  # Активен ли тариф
    display_order = Column(Integer, default=0)  # Порядок отображения в меню