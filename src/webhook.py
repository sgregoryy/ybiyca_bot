from fastapi import APIRouter, Request, Response

yoo_router = APIRouter()
tinkoff_router = APIRouter()
cryptobot_router = APIRouter()


@yoo_router.get('/check-yoo')
async def check_yoo(req: Request):
    try:
        return Response(content='YOOKASSA OK')
    except Exception as e:
        return Response(content=e)
    
    
@yoo_router.post('/yoo-notification')
async def yoo_notify(req: Request):
    pass
    
    
@tinkoff_router.get('/check-tinkoff')
async def check_tinkoff(req: Request):
    try:
        return Response(content='Tinkoff OK')
    except Exception as e:
        return Response(content=e)
    

@tinkoff_router.post('/tinkoff-notification')
async def tinkoff_notify(req: Request):
    pass
    
    
@cryptobot_router.get('/check-cryptobot')
async def check_cryptobot(req: Request):
    try:
        return Response(content='Cryptobot OK')
    except Exception as e:
        return Response(content=e)
    

@cryptobot_router.post('/cryptobot-notification')
async def cryptobot_notify(req: Request):
    pass