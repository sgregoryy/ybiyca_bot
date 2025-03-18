import os
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from aiocryptopay import AioCryptoPay, Networks

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database connection settings"""
    host: str
    port: str
    user: str
    password: str
    database: str
    
    @property
    def url(self) -> str:
        """Get database connection URL"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class TelegramConfig:
    """Telegram bot settings"""
    token: str
    admin_ids: List[int]
    sponsor_channel_id: int
    sponsor_channel_link: str
    require_subscription: bool = False  # Toggle for optional channel subscription


@dataclass
class PaymentConfig:
    """Payment system settings"""
    # Manual payment settings
    manual_payment_enabled: bool = True
    manual_card_number: str = ""
    manual_recipient_name: str = ""
    
    stars_enabled: bool = False
    
    available_methods: List[str] = None
    
    youkassa_enabled: bool = False
    youkassa_shop_id: Optional[str] = None
    youkassa_secret_key: Optional[str] = None
    
    tinkoff_enabled: bool = False
    tinkoff_terminal_key: Optional[str] = None
    tinkoff_secret_key: Optional[str] = None
    
    cryptobot_enabled: bool = False
    cryptobot_token: Optional[str] = None
    
    @property
    def cryptobot(self) -> AioCryptoPay:
        return AioCryptoPay(token=self.cryptobot_token, network=Networks.MAIN_NET)


@dataclass
class TariffConfig:
    """Tariff plan settings"""
    default_plans: List[Dict[str, Any]]


@dataclass
class ChannelConfig:
    """Channel access configuration"""
    multi_channel_mode: bool = False  # Multiple channels mode
    sponsor_channel_id: Optional[int] = None  # Sponsor channel ID
    sponsor_channel_link: Optional[str] = None  # Sponsor channel link


@dataclass
class LocalizationConfig:
    """Localization settings"""
    default_language: str = "ru"
    available_languages: List[str] = None


@dataclass
class WebAppConfig:
    """Web application settings for payment notifications"""
    host: str = "0.0.0.0"
    port: int = 8000
    webhook_base_url: str = 'localhost'


@dataclass
class Config:
    """Main application configuration"""
    db: DatabaseConfig
    telegram: TelegramConfig
    payment: PaymentConfig
    tariff: TariffConfig
    localization: LocalizationConfig
    channels: ChannelConfig
    webapp: WebAppConfig
    debug: bool = False


def load_config(env_path: Optional[str] = None) -> Config:
    """Load configuration from environment variables"""
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()
        
    multi_channel_mode = os.getenv('MULTI_CHANNEL_MODE', '').lower() in ('true', '1', 'yes')
    
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    admin_ids = []
    if admin_ids_str:
        try:
            admin_ids = [int(id.strip()) for id in admin_ids_str.split(',')]
        except ValueError:
            logger.error("Invalid admin IDs format, should be comma-separated integers")

    payment_methods = []
    
    manual_payment_enabled = os.getenv('MANUAL_PAYMENT_ENABLED', 'true').lower() in ('true', '1', 'yes')
    if manual_payment_enabled:
        payment_methods.append('manual')
    
    stars_enabaled = os.getenv('STARS_ENABLED', 'false').lower() in ('true', '1', 'yes')
    if stars_enabaled:
        payment_methods.append('stars')
    
    youkassa_enabled = os.getenv('YOUKASSA_ENABLED', '').lower() in ('true', '1', 'yes')
    if youkassa_enabled and os.getenv('YOUKASSA_SHOP_ID') and os.getenv('YOUKASSA_SECRET_KEY'):
        payment_methods.append('youkassa')
    
    tinkoff_enabled = os.getenv('TINKOFF_ENABLED', '').lower() in ('true', '1', 'yes')
    if tinkoff_enabled and os.getenv('TINKOFF_TERMINAL_KEY') and os.getenv('TINKOFF_SECRET_KEY'):
        payment_methods.append('tinkoff')
    
    cryptobot_enabled = os.getenv('CRYPTOBOT_ENABLED', '').lower() in ('true', '1', 'yes')
    if cryptobot_enabled and os.getenv('CRYPTOBOT_TOKEN'):
        payment_methods.append('cryptobot')
    
    default_plans = [
        {"name": "1 месяц", "code": "1_month", "price": 999, "duration_days": 30, "display_order": 1},
        {"name": "3 месяца", "code": "3_months", "price": 2900, "duration_days": 90, "display_order": 2},
        {"name": "6 месяцев", "code": "6_months", "price": 5500, "duration_days": 180, "display_order": 3},
        {"name": "1 год", "code": "1_year", "price": 7000, "duration_days": 365, "display_order": 4},
    ]
    
    multi_channel_mode = os.getenv('MULTI_CHANNEL_MODE', '').lower() in ('true', '1', 'yes')
    
    channels = []
    if multi_channel_mode:
        channel_count = int(os.getenv('CHANNEL_COUNT', '0'))
        for i in range(1, channel_count + 1):
            channel_id = os.getenv(f'CHANNEL_{i}_ID')
            channel_link = os.getenv(f'CHANNEL_{i}_LINK')
            channel_name = os.getenv(f'CHANNEL_{i}_NAME', f'Channel {i}')
            
            if channel_id and channel_link:
                channels.append({
                    "id": int(channel_id),
                    "link": channel_link,
                    "name": channel_name
                })
    else:
        sponsor_channel_id = os.getenv('SPONSOR_CHANNEL_ID')
        sponsor_channel_link = os.getenv('SPONSOR_CHANNEL_LINK')
        if sponsor_channel_id and sponsor_channel_link:
            channels.append({
                "id": int(sponsor_channel_id),
                "link": sponsor_channel_link,
                "name": "Sponsor Channel"
            })
    
    available_languages = os.getenv('AVAILABLE_LANGUAGES', 'ru,en').split(',')
    
    return Config(
        db=DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASS', ''),
            database=os.getenv('DB_NAME', 'subscription_bot')
        ),
        telegram=TelegramConfig(
            token=os.getenv('BOT_TOKEN', ''),
            admin_ids=admin_ids,
            sponsor_channel_id=int(os.getenv('SPONSOR_CHANNEL_ID', '0')),
            sponsor_channel_link=os.getenv('SPONSOR_CHANNEL_LINK', ''),
            require_subscription=os.getenv('REQUIRE_SUBSCRIPTION', 'true').lower() in ('true', '1', 'yes')
        ),
        payment=PaymentConfig(
            manual_payment_enabled=manual_payment_enabled,
            manual_card_number=os.getenv('MANUAL_CARD_NUMBER', ''),
            manual_recipient_name=os.getenv('MANUAL_RECIPIENT_NAME', ''),
            stars_enabled=stars_enabaled,
            available_methods=payment_methods,
            youkassa_enabled=youkassa_enabled,
            youkassa_shop_id=os.getenv('YOUKASSA_SHOP_ID'),
            youkassa_secret_key=os.getenv('YOUKASSA_SECRET_KEY'),
            tinkoff_enabled=tinkoff_enabled,
            tinkoff_terminal_key=os.getenv('TINKOFF_TERMINAL_KEY'),
            tinkoff_secret_key=os.getenv('TINKOFF_SECRET_KEY'),
            cryptobot_enabled=cryptobot_enabled,
            cryptobot_token=os.getenv('CRYPTOBOT_TOKEN')
        ),
        tariff=TariffConfig(
            default_plans=default_plans
        ),
        localization=LocalizationConfig(
            default_language=os.getenv('DEFAULT_LANGUAGE', 'ru'),
            available_languages=available_languages
        ),
        channels=ChannelConfig(
            multi_channel_mode=multi_channel_mode,
            sponsor_channel_id=int(os.getenv('SPONSOR_CHANNEL_ID', '0')),
            sponsor_channel_link=os.getenv('SPONSOR_CHANNEL_LINK', '')
        ),
        webapp=WebAppConfig(
            host=os.getenv('WEB_HOST', '0.0.0.0'),
            port=int(os.getenv('WEB_PORT', '8000')),
            webhook_base_url=os.getenv('WEB_URL', 'localhost')
        ),
        debug=os.getenv('DEBUG', '').lower() in ('true', '1', 'yes')
    )


config = load_config()