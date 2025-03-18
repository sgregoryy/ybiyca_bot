from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.db.database import Base
import enum


class SubscriptionPlan(enum.Enum):
    MONTH_1 = "1_month"
    MONTH_3 = "3_months"
    MONTH_6 = "6_months"
    YEAR_1 = "1_year"


class Currency(Base):
    """Валюты и способы оплаты"""

    __tablename__ = "currencies"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    requires_manual_confirmation = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    tariff_prices = relationship("TariffPrice", back_populates="currency")
    payment_methods = relationship("PaymentMethodCurrency", back_populates="currency")


class PaymentMethod(Base):
    """Способы оплаты"""

    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=False, unique=True)
    default_currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)
    price_modifier = Column(Float, default=0.0)
    fixed_fee = Column(Float, default=0.0)
    settings = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    default_currency = relationship("Currency", foreign_keys=[default_currency_id])
    supported_currencies = relationship("PaymentMethodCurrency", back_populates="payment_method")


class PaymentMethodCurrency(Base):
    """Связь между способами оплаты и поддерживаемыми валютами"""

    __tablename__ = "payment_method_currencies"

    id = Column(Integer, primary_key=True)
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"), nullable=False)
    currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)
    is_default = Column(Boolean, default=False)

    payment_method = relationship("PaymentMethod", back_populates="supported_currencies")
    currency = relationship("Currency", back_populates="payment_methods")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)
    language = Column(String(10), default="ru")

    subscriptions = relationship("Subscription", back_populates="user")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("tariff_plans.id"), nullable=False)
    start_date = Column(DateTime, server_default=func.now())
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="subscriptions")
    plan = relationship("TariffPlan")


class Channel(Base):
    """Channel access configuration"""

    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    invite_link = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)

    tariff_plans = relationship("TariffPlan", back_populates="channel")


class TariffPlan(Base):
    __tablename__ = "tariff_plans"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=False, unique=True)
    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    prices = relationship("TariffPrice", back_populates="tariff")
    channel = relationship("Channel", back_populates="tariff_plans")


class TariffPrice(Base):
    """Цены тарифов в разных валютах"""

    __tablename__ = "tariff_prices"

    id = Column(Integer, primary_key=True)
    tariff_id = Column(Integer, ForeignKey("tariff_plans.id"), nullable=False)
    currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)
    price = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    tariff = relationship("TariffPlan", back_populates="prices")
    currency = relationship("Currency", back_populates="tariff_prices")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("tariff_plans.id"), nullable=False)
    currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"), nullable=False)
    amount = Column(Float, nullable=False)
    screenshot_file_id = Column(String, nullable=True)
    external_id = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)

    user = relationship("User")
    plan = relationship("TariffPlan")
    currency = relationship("Currency")
    payment_method = relationship("PaymentMethod")
