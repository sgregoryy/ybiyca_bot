from aiogram.fsm.state import StatesGroup, State

class PaymentStates(StatesGroup):
    waiting_for_payment_screenshot = State()
    waiting_for_admin_approval = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast_message = State()
    waiting_for_tariff_name = State()
    waiting_for_tariff_price = State()
    waiting_for_tariff_duration = State()
    waiting_for_tariff_edit_id = State()
    waiting_for_tariff_field = State()
    waiting_for_tariff_new_value = State()