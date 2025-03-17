import asyncio
import logging
import signal
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import config
from src.db.database import init_db, close_db_connection
from src.db.DALS.tariff import TariffDAL
from src.handlers import start, subscription, payment, admin, admin_tariff
from src.filters.admin import AdminFilter


logging.basicConfig(
    level=logging.INFO if not config.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)


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


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("Инициализация базы данных...")
    await init_db()
    
    logger.info("Инициализация тарифных планов...")
    await init_tariff_plans()
    
    logger.info("Бот успешно запущен!")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Закрытие соединений с базой данных...")
    await close_db_connection()
    
    logger.info("Бот остановлен")


async def main():
    """Точка входа в приложение"""
    # Инициализация бота и диспетчера
    bot = Bot(token=config.telegram.token, parse_mode="HTML")
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация хендлеров запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Регистрация маршрутизаторов
    dp.include_router(start.router)
    dp.include_router(subscription.router)
    dp.include_router(payment.router)
    dp.include_router(admin.router)
    dp.include_router(admin_tariff.router)
    
    async def signal_handler(signum):
        logger.info(f"Получен сигнал {signum.name}, завершение работы...")
        await dp.stop_polling()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(
            sig, lambda sig=sig: asyncio.create_task(signal_handler(sig))
        )
    

    try:
        logger.info("Запуск бота...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот был остановлен вручную")
    except Exception as e:
        logger.error(f"Необработанное исключение: {e}")