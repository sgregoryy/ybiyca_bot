import logging
import os

def setup_logging():
    """Настройка базового логирования"""

    os.makedirs("logs", exist_ok=True)
    

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    

    file_handler = logging.FileHandler("logs/shipment_bot.log", encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))
    

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    

    logging.basicConfig(
        level=getattr(logging, "INFO"),
        handlers=[file_handler, console_handler],
        format=log_format,
        encoding='utf-8'
    )
    
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)