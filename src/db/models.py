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

# Модель валюты
class Currency(Base):
    """Валюты и способы оплаты"""
    __tablename__ = "currencies"
    
    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)  # RUB, USD, BTC, ETH, STARS
    name = Column(String, nullable=False)  # Российский рубль, Доллар США, Bitcoin и т.д.
    symbol = Column(String, nullable=False)  # ₽, $, ₿
    is_active = Column(Boolean, default=True)  # Активна ли валюта
    requires_manual_confirmation = Column(Boolean, default=False)  # Требует ли ручного подтверждения
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    tariff_prices = relationship("TariffPrice", back_populates="currency")
    payment_methods = relationship("PaymentMethodCurrency", back_populates="currency")

# Модель способа оплаты
class PaymentMethod(Base):
    """Способы оплаты"""
    __tablename__ = "payment_methods"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Название способа оплаты
    code = Column(String, nullable=False, unique=True)  # Уникальный код (manual, youkassa, tinkoff, cryptobot)
    default_currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)  # Валюта по умолчанию
    price_modifier = Column(Float, default=0.0)  # Модификатор цены в процентах
    fixed_fee = Column(Float, default=0.0)  # Фиксированная комиссия
    settings = Column(String, nullable=True)  # JSON с настройками
    is_active = Column(Boolean, default=True)  # Активен ли способ оплаты
    display_order = Column(Integer, default=0)  # Порядок отображения
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    default_currency = relationship("Currency", foreign_keys=[default_currency_id])
    supported_currencies = relationship("PaymentMethodCurrency", back_populates="payment_method")

# Связь между способами оплаты и поддерживаемыми валютами
class PaymentMethodCurrency(Base):
    """Связь между способами оплаты и поддерживаемыми валютами"""
    __tablename__ = "payment_method_currencies"
    
    id = Column(Integer, primary_key=True)
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"), nullable=False)
    currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)
    is_default = Column(Boolean, default=False)  # Является ли валютой по умолчанию для данного способа
    
    # Relationships
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
    language = Column(String(10), default="ru")  # Added language field
    
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

# Обновление модели TariffPlan для работы с несколькими валютами
class TariffPlan(Base):
    __tablename__ = "tariff_plans"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Название тарифа (например, "1 месяц")
    code = Column(String, nullable=False, unique=True)  # Код тарифа (например, "1_month")
    price = Column(Float, nullable=False)  # Базовая цена в рублях (для обратной совместимости)
    duration_days = Column(Integer, nullable=False)  # Длительность подписки в днях
    is_active = Column(Boolean, default=True)  # Активен ли тариф
    display_order = Column(Integer, default=0)  # Порядок отображения в меню
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    prices = relationship("TariffPrice", back_populates="tariff")

# Модель для хранения цен в разных валютах
class TariffPrice(Base):
    """Цены тарифов в разных валютах"""
    __tablename__ = "tariff_prices"
    
    id = Column(Integer, primary_key=True)
    tariff_id = Column(Integer, ForeignKey("tariff_plans.id"), nullable=False)
    currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)
    price = Column(Float, nullable=False)  # Цена в выбранной валюте
    is_active = Column(Boolean, default=True)  # Активна ли цена
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    tariff = relationship("TariffPlan", back_populates="prices")
    currency = relationship("Currency", back_populates="tariff_prices")

# Обновленная модель Payment для работы с разными валютами
class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("tariff_plans.id"), nullable=False)
    currency_id = Column(Integer, ForeignKey("currencies.id"), nullable=False)
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"), nullable=False)  # Связь с моделью PaymentMethod
    amount = Column(Float, nullable=False)  # Сумма в указанной валюте
    screenshot_file_id = Column(String, nullable=True)  # ID файла скриншота
    external_id = Column(String, nullable=True)  # Внешний ID транзакции
    status = Column(String, default="pending")  # pending, approved, rejected, cancelled
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)  # Когда платеж был обработан
    notes = Column(String, nullable=True)  # Дополнительные заметки
    
    # Relationships
    user = relationship("User")
    plan = relationship("TariffPlan")
    currency = relationship("Currency")
    payment_method = relationship("PaymentMethod")  # Связь с моделью PaymentMethod

class Channel(Base):
    """Channel access configuration"""
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Channel name
    channel_id = Column(BigInteger, nullable=False)  # Telegram channel ID
    invite_link = Column(String, nullable=False)  # Invite link to the channel
    is_active = Column(Boolean, default=True)  # Is the channel active
    display_order = Column(Integer, default=0)  # Order in the channels list
    
    # Relationships
    access_plans = relationship("ChannelAccessPlan", back_populates="channel")

class ChannelAccessPlan(Base):
    """Mapping between channels and tariff plans"""
    __tablename__ = "channel_access_plans"
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("tariff_plans.id"), nullable=False)
    
    # Relationships
    channel = relationship("Channel", back_populates="access_plans")
    plan = relationship("TariffPlan")