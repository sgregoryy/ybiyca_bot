import asyncio
import logging
import platform
import signal
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from fastapi import FastAPI

from src.db.DALS.currency import CurrencyDAL
from src.db.DALS.payment_method import PaymentMethodDAL
from src.db.DALS.channel import ChannelDAL
from src.config import config
from src.db.database import init_db, close_db_connection
from src.db.DALS.tariff import TariffDAL
from src.handlers import start, subscription, payment, admin, admin_tariff
from src.payments import stars
from src.filters.admin import AdminFilter
from src.filters.sub import SubscriptionFilter
from src.webhook import yoo_router, tinkoff_router, cryptobot_router


logging.basicConfig(
    level=logging.INFO if not config.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)


"""
Функция для инициализации методов оплаты, включая звезды
"""

async def init_payment_methods():
    """Инициализация методов оплаты"""
    from src.db.DALS.currency import CurrencyDAL
    from src.db.DALS.payment_method import PaymentMethodDAL
    
    logger.info("Инициализация методов оплаты и валют...")
    
    # Инициализируем валюты - только рубль
    default_currencies = [
        {"code": "RUB", "name": "Российский рубль", "symbol": "₽", "requires_manual_confirmation": True}
    ]
    
    # Создаем валюты по одной
    for currency_data in default_currencies:
        try:
            currency = await CurrencyDAL.get_by_code(currency_data["code"])
            if not currency:
                await CurrencyDAL.create_currency(
                    code=currency_data["code"],
                    name=currency_data["name"],
                    symbol=currency_data["symbol"],
                    requires_manual_confirmation=currency_data["requires_manual_confirmation"]
                )
                logger.info(f"Валюта {currency_data['code']} создана")
            else:
                logger.info(f"Валюта {currency_data['code']} уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании валюты {currency_data['code']}: {e}")
    
    # Дополнительно создаем валюту STARS, если включена оплата звездами
    if config.payment.stars_enabled:
        try:
            stars_currency = await CurrencyDAL.get_by_code("STARS")
            if not stars_currency:
                await CurrencyDAL.create_currency(
                    code="STARS",
                    name="Telegram Stars",
                    symbol="⭐",
                    requires_manual_confirmation=False
                )
                logger.info("Валюта STARS создана")
            else:
                logger.info("Валюта STARS уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании валюты STARS: {e}")
    
    # Инициализируем методы оплаты
    
    # Ручной платеж (карта)
    if config.payment.manual_payment_enabled:
        try:
            manual_method = await PaymentMethodDAL.get_by_code("manual")
            if not manual_method:
                await PaymentMethodDAL.create_method(
                    name="Банковская карта (вручную)",
                    code="manual",
                    price_modifier=0,
                    fixed_fee=0
                )
                logger.info("Метод оплаты 'manual' создан")
            else:
                logger.info("Метод оплаты 'manual' уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании метода оплаты 'manual': {e}")
    
    # ЮKassa
    if config.payment.youkassa_enabled:
        try:
            youkassa_method = await PaymentMethodDAL.get_by_code("youkassa")
            if not youkassa_method:
                await PaymentMethodDAL.create_method(
                    name="Банковская карта (ЮKassa)",
                    code="youkassa",
                    price_modifier=0,
                    fixed_fee=0
                )
                logger.info("Метод оплаты 'youkassa' создан")
            else:
                logger.info("Метод оплаты 'youkassa' уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании метода оплаты 'youkassa': {e}")
    
    # Tinkoff
    if config.payment.tinkoff_enabled:
        try:
            tinkoff_method = await PaymentMethodDAL.get_by_code("tinkoff")
            if not tinkoff_method:
                await PaymentMethodDAL.create_method(
                    name="Банковская карта (Tinkoff)",
                    code="tinkoff",
                    price_modifier=0,
                    fixed_fee=0
                )
                logger.info("Метод оплаты 'tinkoff' создан")
            else:
                logger.info("Метод оплаты 'tinkoff' уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании метода оплаты 'tinkoff': {e}")
    
    # Звезды Telegram
    if config.payment.stars_enabled:
        try:
            stars_method = await PaymentMethodDAL.get_by_code("stars")
            if not stars_method:
                await PaymentMethodDAL.create_method(
                    name="Звезды Telegram",
                    code="stars",
                    price_modifier=0,
                    fixed_fee=0
                )
                logger.info("Метод оплаты 'stars' создан")
            else:
                logger.info("Метод оплаты 'stars' уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании метода оплаты 'stars': {e}")
    
    # CryptoBot
    if config.payment.cryptobot_enabled:
        try:
            crypto_method = await PaymentMethodDAL.get_by_code("cryptobot")
            if not crypto_method:
                await PaymentMethodDAL.create_method(
                    name="Криптовалюта",
                    code="cryptobot",
                    price_modifier=0,
                    fixed_fee=0
                )
                logger.info("Метод оплаты 'cryptobot' создан")
            else:
                logger.info("Метод оплаты 'cryptobot' уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании метода оплаты 'cryptobot': {e}")
    
    logger.info("Методы оплаты инициализированы")


def is_web_service_needed() -> bool:
    """Проверяет, нужен ли веб-сервис на основе конфигурации"""
    return any([
        config.payment.youkassa_enabled,
        config.payment.tinkoff_enabled,
        config.payment.cryptobot_enabled,
    ])


async def create_fastapi_app() -> FastAPI:
    """Создание FastAPI приложения"""
    app = FastAPI(
        title="Subscription Bot API",
        description="API for Telegram subscription bot",
        version="1.0.0",
    )

    if config.payment.youkassa_enabled:
        app.include_router(yoo_router, prefix="/payments/youkassa", tags=["YouKassa"])
        logger.info("YouKassa платежный роутер подключен")
    
    if config.payment.tinkoff_enabled:
        app.include_router(tinkoff_router, prefix="/payments/tinkoff", tags=["Tinkoff"])
        logger.info("Tinkoff платежный роутер подключен")
    
    if config.payment.cryptobot_enabled:
        app.include_router(cryptobot_router, prefix="/payments/cryptobot", tags=["CryptoBot"])
        logger.info("CryptoBot платежный роутер подключен")

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
        
    return app


async def init_tariff_plans():
    """Инициализация тарифных планов"""
    default_plans = [
        {"name": "1 месяц", "code": "1_month", "price": 999, "duration_days": 30, "display_order": 1},
        {"name": "3 месяца", "code": "3_months", "price": 2900, "duration_days": 90, "display_order": 2},
        {"name": "6 месяцев", "code": "6_months", "price": 5500, "duration_days": 180, "display_order": 3},
        {"name": "1 год", "code": "1_year", "price": 7000, "duration_days": 365, "display_order": 4},
    ]
    
    await TariffDAL.initialize_default_plans(default_plans)
    logger.info("Тарифные планы инициализированы")


async def init_channels():
    """Инициализация каналов"""
    if config.telegram.require_subscription and config.telegram.sponsor_channel_id:
        sponsor_channel = await ChannelDAL.get_by_telegram_id(config.telegram.sponsor_channel_id)
        
        if not sponsor_channel:
            await ChannelDAL.create_channel(
                name="Спонсорский канал",
                channel_id=config.telegram.sponsor_channel_id,
                invite_link=config.telegram.sponsor_channel_link
            )
            logger.info("Спонсорский канал инициализирован")
        
    logger.info("Каналы инициализированы")


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("Инициализация базы данных...")
    await init_db()
    
    logger.info("Инициализация тарифных планов...")
    await init_tariff_plans()
    
    logger.info("Инициализация методов оплаты...")
    await init_payment_methods()
    
    logger.info("Инициализация каналов...")
    await init_channels()
    
    logger.info("Бот успешно запущен!")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Закрытие соединений с базой данных...")
    await close_db_connection()
    
    logger.info("Бот остановлен")


async def start_polling(bot: Bot, dp: Dispatcher):
    """Запуск бота в режиме long polling"""
    logger.info("Запуск бота в режиме long polling...")
    await dp.start_polling(bot)


async def start_bot_with_web_service(bot: Bot, dp: Dispatcher):
    """Запуск бота в режиме long polling с отдельным веб-сервисом"""
    fastapi_app = await create_fastapi_app()
    
    bot_task = asyncio.create_task(start_polling(bot, dp))
    
    web_config = uvicorn.Config(
        app=fastapi_app,
        host=config.webapp.host,
        port=config.webapp.port,
        log_level="debug" if config.debug else "info"
    )
    web_server = uvicorn.Server(web_config)
    web_task = asyncio.create_task(web_server.serve())
    
    logger.info(f"Запуск бота в режиме long polling с отдельным веб-сервисом на {config.webapp.host}:{config.webapp.port}...")
    
    try:
        done, pending = await asyncio.wait(
            [bot_task, web_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        for task in pending:
            task.cancel()
            
        await asyncio.gather(*pending, return_exceptions=True)
        
    except asyncio.CancelledError:
        bot_task.cancel()
        web_task.cancel()
        await asyncio.gather(bot_task, web_task, return_exceptions=True)


"""
Обновления для основного файла __main__.py
"""

async def main():
    """Точка входа в приложение"""
    # Инициализация бота и диспетчера
    bot = Bot(token=config.telegram.token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация хендлеров запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Регистрация фильтров
    if config.telegram.require_subscription:
        dp.message.filter(SubscriptionFilter())
    
    # Регистрация маршрутизаторов
    dp.include_router(start.router)
    dp.include_router(subscription.router)
    dp.include_router(payment.router)
    dp.include_router(stars.router)  # Добавляем маршрутизатор для звезд
    dp.include_router(admin.router)
    dp.include_router(admin_tariff.router)
    
    # Настройка обработчиков сигналов для корректного завершения
    loop = asyncio.get_running_loop()
    
    stop_event = asyncio.Event()
    
    def signal_handler(signum):
        logger.info(f"Получен сигнал {signum.name}, завершение работы...")
        if not stop_event.is_set():
            stop_event.set()
    
    # На Windows обработчики сигналов не поддерживаются
    if platform.system() != "Windows":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, lambda sig=sig: signal_handler(sig)
            )
    
    try:
        if is_web_service_needed():
            # Запуск в режиме long polling с отдельным веб-сервисом
            await start_bot_with_web_service(bot, dp)
        else:
            # Запуск только бота в режиме long polling
            await start_polling(bot, dp)
            
    except Exception as e:
        logger.error(f"Необработанное исключение: {e}")
    finally:
        # Освобождаем ресурсы
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот был остановлен вручную")
    except Exception as e:
        logger.error(f"Необработанное исключение: {e}")