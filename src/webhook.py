from fastapi import APIRouter, Request, Response, HTTPException, Depends
import json
import logging
from src.payments.youkassa import process_payment_notification as process_youkassa_notification
from src.payments.tinkoff import process_payment_notification as process_tinkoff_notification
from src.payments.cryptobot import process_crypto_payment as process_cryptobot_notification
from src.config import config

logger = logging.getLogger(__name__)

yoo_router = APIRouter()
tinkoff_router = APIRouter()
cryptobot_router = APIRouter()


@yoo_router.get('/check-yoo')
async def check_yoo(req: Request):
    try:
        return Response(content='YOOKASSA OK')
    except Exception as e:
        logger.error(f"Error in check_yoo: {e}")
        return Response(content=str(e))
    
    
@yoo_router.post('/yoo-notification')
async def yoo_notify(req: Request):
    try:
        body = await req.body()
        notification = json.loads(body)
        
        #TODO: Добавить проверку подписи
        result = await process_youkassa_notification(notification)
        
        if result:
            return Response(content="OK", status_code=200)
        else:
            logger.warning(f"Failed to process YouKassa notification: {notification}")
            return Response(content="Ok", status_code=200)
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in YouKassa notification")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.exception(f"Error processing YouKassa notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
@tinkoff_router.get('/check-tinkoff')
async def check_tinkoff(req: Request):
    try:
        return Response(content='Tinkoff OK')
    except Exception as e:
        logger.error(f"Error in check_tinkoff: {e}")
        return Response(content=str(e))
    

@tinkoff_router.post('/tinkoff-notification')
async def tinkoff_notify(req: Request):
    try:
        body = await req.body()
        notification = json.loads(body)
        
        result = await process_tinkoff_notification(notification)
        
        if result:
            return Response(content="OK", status_code=200)
        else:
            logger.warning(f"Failed to process Tinkoff notification: {notification}")
            return Response(content="Processing failed", status_code=500)
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Tinkoff notification")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.exception(f"Error processing Tinkoff notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
@cryptobot_router.get('/check-cryptobot')
async def check_cryptobot(req: Request):
    try:
        return Response(content='Cryptobot OK')
    except Exception as e:
        logger.error(f"Error in check_cryptobot: {e}")
        return Response(content=str(e))
    

@cryptobot_router.post('/cryptobot-notification')
async def cryptobot_notify(req: Request):
    try:
        body = await req.body()
        notification = json.loads(body)
        
        result = await process_cryptobot_notification(notification)
        
        if result:
            return Response(content="OK", status_code=200)
        else:
            logger.warning(f"Failed to process Cryptobot notification: {notification}")
            return Response(content="Processing failed", status_code=500)
            
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Cryptobot notification")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.exception(f"Error processing Cryptobot notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))