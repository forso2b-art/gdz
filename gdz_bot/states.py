from aiogram.fsm.state import State, StatesGroup


class SolveStates(StatesGroup):
    waiting_for_task = State()


class AdminStates(StatesGroup):
    waiting_for_setting_value = State()
    waiting_for_subscription_days = State()
