from __future__ import annotations

from math import ceil

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from gdz_bot.constants import ADMIN_PAGE_SIZE, GRADES, get_subject_label, get_subjects_for_grade


def main_menu_kb(*, is_admin: bool, has_selection: bool, has_class: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎓 Выбрать класс", callback_data="menu:class")
    kb.button(text="📚 Выбрать предмет", callback_data="menu:subject")
    if has_selection:
        kb.button(text="📝 Загрузить задание", callback_data="menu:solve")
    kb.button(text="💼 Мой доступ", callback_data="menu:access")
    kb.button(text="💎 Тарифы", callback_data="menu:tariffs")
    kb.button(text="🕘 История", callback_data="menu:history")
    kb.button(text="❓ Как это работает", callback_data="menu:help")
    if is_admin:
        kb.button(text="🛠️ Админ-панель", callback_data="menu:admin")
    sizes = [2]
    if has_selection:
        sizes.append(1)
    sizes.extend([2, 2])
    if is_admin:
        sizes.append(1)
    kb.adjust(*sizes)
    return kb.as_markup()


def grades_kb(selected_grade: int | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for grade in GRADES:
        label = f"✅ {grade} класс" if grade == selected_grade else f"🎓 {grade} класс"
        kb.button(text=label, callback_data=f"grade:{grade}")
    kb.button(text="⬅️ Назад", callback_data="menu:home")
    kb.adjust(2, 2, 2, 2, 2, 1)
    return kb.as_markup()


def subjects_kb(grade: int, selected_subject: str | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for subject_key, label in get_subjects_for_grade(grade):
        button_label = f"✅ {label}" if subject_key == selected_subject else f"📘 {label}"
        kb.button(text=button_label, callback_data=f"subject:{grade}:{subject_key}")
    kb.button(text="⬅️ Назад", callback_data="menu:class")
    kb.adjust(2, 2, 2, 2, 2, 1)
    return kb.as_markup()


def solve_prompt_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Сменить предмет", callback_data="menu:subject")
    kb.button(text="🏠 Меню", callback_data="menu:home")
    kb.adjust(2)
    return kb.as_markup()


def result_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Решить еще", callback_data="menu:solve")
    kb.button(text="🕘 История", callback_data="menu:history")
    kb.button(text="🏠 Меню", callback_data="menu:home")
    kb.adjust(2, 1)
    return kb.as_markup()


def access_kb(*, is_premium: bool, has_pending_request: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not is_premium and not has_pending_request:
        kb.button(text="💎 Оформить премиум", callback_data="premium:request")
    if has_pending_request:
        kb.button(text="⏳ Заявка отправлена", callback_data="noop")
    kb.button(text="💎 Тарифы", callback_data="menu:tariffs")
    kb.button(text="🏠 Меню", callback_data="menu:home")
    kb.adjust(1, 2)
    return kb.as_markup()


def tariffs_kb(*, is_premium: bool, has_pending_request: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not is_premium and not has_pending_request:
        kb.button(text="📨 Отправить заявку", callback_data="premium:request")
    kb.button(text="💼 Мой доступ", callback_data="menu:access")
    kb.button(text="🏠 Меню", callback_data="menu:home")
    kb.adjust(1, 2)
    return kb.as_markup()


def history_kb(requests: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in requests:
        label = f"📄 #{item['id']} {get_subject_label(item['subject_key'])}"
        kb.button(text=label[:32], callback_data=f"req:{item['id']}")
    kb.button(text="🏠 Меню", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def request_detail_kb(*, is_admin: bool, user_id: int | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if is_admin and user_id:
        kb.button(text="👤 К пользователю", callback_data=f"admin:user:{user_id}")
    kb.button(text="🕘 История", callback_data="menu:history")
    kb.button(text="🏠 Меню", callback_data="menu:home")
    if is_admin and user_id:
        kb.adjust(1, 2)
    else:
        kb.adjust(2)
    return kb.as_markup()


def admin_main_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="admin:stats")
    kb.button(text="👥 Пользователи", callback_data="admin:users:1")
    kb.button(text="📨 Заявки", callback_data="admin:subreqs")
    kb.button(text="⚙️ Настройки", callback_data="admin:settings")
    kb.button(text="🏠 Меню", callback_data="menu:home")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def admin_users_kb(users: list[dict], page: int, total_users: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for user in users:
        prefix = "🛡️" if user["is_admin"] else "⭐" if user["subscription_expires_at"] else "👤"
        label = f"{prefix} {user['full_name']}"
        kb.button(text=label[:32], callback_data=f"admin:user:{user['user_id']}")

    total_pages = max(ceil(total_users / ADMIN_PAGE_SIZE), 1)
    if page > 1:
        kb.button(text="⬅️ Назад", callback_data=f"admin:users:{page - 1}")
    kb.button(text=f"📄 {page}/{total_pages}", callback_data="noop")
    if page < total_pages:
        kb.button(text="➡️ Дальше", callback_data=f"admin:users:{page + 1}")
    kb.button(text="🛠️ Админ-меню", callback_data="menu:admin")
    kb.adjust(1, 1, 1, 1, 3, 1)
    return kb.as_markup()


def admin_user_kb(user: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Выдать 30 дней", callback_data=f"admin:user:grant:{user['user_id']}:30")
    kb.button(text="♾️ Навсегда", callback_data=f"admin:user:grant:{user['user_id']}:9999")
    kb.button(text="🗓️ Свои дни", callback_data=f"admin:user:custom:{user['user_id']}")
    kb.button(text="🚫 Снять премиум", callback_data=f"admin:user:clear:{user['user_id']}")
    kb.button(text="♻️ Сбросить лимит", callback_data=f"admin:user:reset:{user['user_id']}")
    block_flag = 0 if user["is_blocked"] else 1
    block_text = "✅ Разблокировать" if user["is_blocked"] else "⛔ Заблокировать"
    kb.button(text=block_text, callback_data=f"admin:user:block:{user['user_id']}:{block_flag}")
    kb.button(text="🧾 История запросов", callback_data=f"admin:user:history:{user['user_id']}")
    kb.button(text="⬅️ К списку", callback_data="admin:users:1")
    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()


def admin_user_history_kb(user_id: int, requests: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in requests:
        label = f"📄 #{item['id']} {get_subject_label(item['subject_key'])}"
        kb.button(text=label[:32], callback_data=f"req:{item['id']}")
    kb.button(text="👤 К пользователю", callback_data=f"admin:user:{user_id}")
    kb.button(text="⬅️ К списку", callback_data="admin:users:1")
    kb.adjust(1, 1, 1, 2)
    return kb.as_markup()


def admin_subscription_requests_kb(items: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        label = f"📨 #{item['id']} {item['full_name']}"
        kb.button(text=label[:32], callback_data=f"admin:subreq:{item['id']}")
    kb.button(text="🛠️ Админ-меню", callback_data="menu:admin")
    kb.adjust(1)
    return kb.as_markup()


def admin_subscription_request_kb(request_id: int, user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Одобрить 30 дней", callback_data=f"admin:subreq:{request_id}:approve:30")
    kb.button(text="♾️ Одобрить 9999 дней", callback_data=f"admin:subreq:{request_id}:approve:9999")
    kb.button(text="❌ Отклонить", callback_data=f"admin:subreq:{request_id}:reject")
    kb.button(text="👤 Профиль пользователя", callback_data=f"admin:user:{user_id}")
    kb.button(text="⬅️ К заявкам", callback_data="admin:subreqs")
    kb.adjust(2, 1, 1, 1)
    return kb.as_markup()


def admin_settings_kb(settings: dict[str, str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    editable_keys = [
        ("free_daily_limit", f"🔓 Free лимит: {settings['free_daily_limit']}"),
        ("premium_daily_limit", f"💎 Premium лимит: {settings['premium_daily_limit']}"),
        ("default_premium_days", f"📅 Premium дни: {settings['default_premium_days']}"),
        ("free_reasoning_effort", f"🧠 Free think: {settings['free_reasoning_effort']}"),
        ("premium_reasoning_effort", f"🚀 Premium think: {settings['premium_reasoning_effort']}"),
        ("free_system_prompt", "📝 Free prompt"),
        ("premium_system_prompt", "📝 Premium prompt"),
    ]
    for key, label in editable_keys:
        kb.button(text=label[:32], callback_data=f"admin:setting:{key}")
    kb.button(text="🛠️ Админ-меню", callback_data="menu:admin")
    kb.adjust(1)
    return kb.as_markup()
