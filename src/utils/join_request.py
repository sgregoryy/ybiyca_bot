from aiogram import Router, Bot
from aiogram.types import ChatJoinRequest
from src.utils.cron_func import process_join_request
import logging

logger = logging.getLogger(__name__)

router = Router()

@router.chat_join_request()
async def handle_join_request(chat_join_request: ChatJoinRequest, bot: Bot):
    user_id = chat_join_request.from_user.id
    requested_channel_id = chat_join_request.chat.id
    

    has_access = await process_join_request(bot, user_id, requested_channel_id)
    
    if has_access:
        try:

            await chat_join_request.approve()
            logger.info(f"Approved join request to channel {requested_channel_id} from user {user_id}")
        except Exception as e:
            logger.error(f"Error approving join request to channel {requested_channel_id}: {e}")
    else:
        try:
            await chat_join_request.decline()
            
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ Для доступа к этому каналу требуется активная подписка с соответствующим тарифом.\n\n"
                    "Пожалуйста, оформите подписку через бота, используя команду /start или кнопку «💼 Тарифы»."
                )
            )
            logger.info(f"Declined join request to channel {requested_channel_id}: no active subscription with access")
        except Exception as e:
            logger.error(f"Error declining join request: {e}")