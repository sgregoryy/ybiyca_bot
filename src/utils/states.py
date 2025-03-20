from aiogram.fsm.state import StatesGroup, State


class PaymentStates(StatesGroup):
    waiting_for_payment_screenshot = State()
    waiting_for_admin_approval = State()
    waiting_for_payment_method = State()
    waiting_for_payment_confirmation = State()


class AdminStates(StatesGroup):

    waiting_for_broadcast_message = State()

    waiting_for_tariff_name = State()
    waiting_for_tariff_price = State()
    waiting_for_tariff_duration = State()
    waiting_for_tariff_edit_id = State()
    waiting_for_tariff_field = State()
    waiting_for_tariff_new_value = State()

    waiting_for_payment_method_name = State()
    waiting_for_payment_method_code = State()
    waiting_for_payment_method_modifier = State()
    waiting_for_payment_method_fee = State()
    waiting_for_payment_method_field = State()
    waiting_for_payment_method_new_value = State()

    waiting_for_channel_name = State()
    waiting_for_channel_id = State()
    waiting_for_channel_link = State()
    waiting_for_channel_field = State()
    waiting_for_channel_new_value = State()

    waiting_for_confirmation = State()
    
    waiting_for_welcome_message = State()
