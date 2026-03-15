from __future__ import annotations

from aiogram import F, Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from gdz_bot.config import Config
from gdz_bot.db import Database
from gdz_bot.keyboards import (
    admin_main_kb,
    admin_settings_kb,
    admin_subscription_request_kb,
    admin_subscription_requests_kb,
    admin_user_history_kb,
    admin_user_kb,
    admin_users_kb,
)
from gdz_bot.states import AdminStates
from gdz_bot.texts import (
    render_admin_settings,
    render_admin_stats,
    render_admin_user,
    render_admin_user_history,
    render_subscription_request,
    render_subscription_requests,
    subscription_is_active,
)

admin_router = Router(name="admin")

INT_SETTINGS = {"free_daily_limit", "premium_daily_limit", "default_premium_days"}
FLOAT_SETTINGS = {"free_temperature", "premium_temperature"}


async def _edit_or_send(target: Message | CallbackQuery, text: str, **kwargs):
    if isinstance(target, CallbackQuery) and target.message:
        try:
            return await target.message.edit_text(text, **kwargs)
        except TelegramBadRequest:
            return await target.message.answer(text, **kwargs)
    if isinstance(target, CallbackQuery):
        return await target.answer(text, show_alert=True)
    return await target.answer(text, **kwargs)


async def _require_admin(target: Message | CallbackQuery, db: Database) -> dict | None:
    user = await db.upsert_user(target.from_user)
    if not user["is_admin"]:
        if isinstance(target, CallbackQuery):
            await target.answer("Недостаточно прав", show_alert=True)
        else:
            await target.answer("Недостаточно прав")
        return None
    return user


def _daily_limit_for_user(user: dict, settings: dict[str, str], config: Config) -> tuple[int, int]:
    premium = subscription_is_active(user, config.timezone)
    daily_limit = int(settings["premium_daily_limit" if premium else "free_daily_limit"])
    used = int(user["daily_requests"])
    return daily_limit, max(daily_limit - used, 0)


async def _show_admin_menu(target: Message | CallbackQuery, db: Database) -> None:
    admin = await _require_admin(target, db)
    if admin is None:
        return
    await _edit_or_send(target, "<b>Админ-панель</b>\nВыбери раздел управления.", reply_markup=admin_main_kb())


async def _show_user_card(target: Message | CallbackQuery, db: Database, config: Config, user_id: int) -> None:
    admin = await _require_admin(target, db)
    if admin is None:
        return

    user = await db.get_user(user_id, refresh_daily_usage=True)
    if user is None:
        await _edit_or_send(target, "Пользователь не найден.")
        return

    settings = await db.get_settings_map()
    daily_limit, remaining = _daily_limit_for_user(user, settings, config)
    await _edit_or_send(
        target,
        render_admin_user(user, timezone=config.timezone, daily_limit=daily_limit, remaining=remaining),
        reply_markup=admin_user_kb(user),
    )


@admin_router.callback_query(F.data == "menu:admin")
async def admin_menu_callback(callback: CallbackQuery, db: Database) -> None:
    await _show_admin_menu(callback, db)


@admin_router.callback_query(F.data == "admin:stats")
async def admin_stats_callback(callback: CallbackQuery, db: Database) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    stats = await db.get_stats()
    await callback.answer()
    await _edit_or_send(callback, render_admin_stats(stats), reply_markup=admin_main_kb())


@admin_router.callback_query(F.data.startswith("admin:users:"))
async def admin_users_callback(callback: CallbackQuery, db: Database) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    page = max(int(callback.data.split(":")[2]), 1)
    users = await db.list_users(page=page)
    total_users = await db.count_users()
    await callback.answer()
    await _edit_or_send(
        callback,
        "<b>Пользователи</b>\nОткрой карточку нужного пользователя.",
        reply_markup=admin_users_kb(users, page=page, total_users=total_users),
    )


@admin_router.callback_query(F.data.startswith("admin:user:history:"))
async def admin_user_history_callback(callback: CallbackQuery, db: Database) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    user_id = int(callback.data.split(":")[3])
    user = await db.get_user(user_id)
    if user is None:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    requests = await db.list_recent_requests(user_id, limit=10)
    await callback.answer()
    await _edit_or_send(
        callback,
        render_admin_user_history(user, requests),
        reply_markup=admin_user_history_kb(user_id, requests),
    )


@admin_router.callback_query(F.data.startswith("admin:user:grant:"))
async def admin_grant_callback(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    _, _, _, user_id_raw, days_raw = callback.data.split(":")
    user_id = int(user_id_raw)
    days = int(days_raw)
    await db.extend_subscription(user_id, days)
    try:
        await bot.send_message(user_id, f"Тебе активировали Premium на <b>{days}</b> дней.")
    except Exception:
        pass
    await callback.answer("Подписка обновлена")
    await _show_user_card(callback, db, config, user_id)


@admin_router.callback_query(F.data.startswith("admin:user:custom:"))
async def admin_custom_days_callback(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    user_id = int(callback.data.split(":")[3])
    await state.set_state(AdminStates.waiting_for_subscription_days)
    await state.update_data(target_user_id=user_id)
    await callback.answer()
    await _edit_or_send(
        callback,
        (
            f"<b>Выдать подписку пользователю {user_id}</b>\n"
            "Следующим сообщением отправь количество дней целым числом."
        ),
        reply_markup=admin_main_kb(),
    )


@admin_router.callback_query(F.data.startswith("admin:user:clear:"))
async def admin_clear_subscription_callback(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    user_id = int(callback.data.split(":")[3])
    await db.clear_subscription(user_id)
    try:
        await bot.send_message(user_id, "Твоя Premium-подписка была отключена.")
    except Exception:
        pass
    await callback.answer("Подписка снята")
    await _show_user_card(callback, db, config, user_id)


@admin_router.callback_query(F.data.startswith("admin:user:reset:"))
async def admin_reset_limit_callback(callback: CallbackQuery, db: Database, config: Config) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    user_id = int(callback.data.split(":")[3])
    await db.reset_user_daily_limit(user_id)
    await callback.answer("Лимит сброшен")
    await _show_user_card(callback, db, config, user_id)


@admin_router.callback_query(F.data.startswith("admin:user:block:"))
async def admin_block_callback(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    _, _, _, user_id_raw, flag_raw = callback.data.split(":")
    user_id = int(user_id_raw)
    blocked = bool(int(flag_raw))
    await db.set_blocked(user_id, blocked)
    try:
        await bot.send_message(
            user_id,
            "Твой аккаунт заблокирован." if blocked else "Твой аккаунт снова активен.",
        )
    except Exception:
        pass
    await callback.answer("Статус обновлен")
    await _show_user_card(callback, db, config, user_id)


@admin_router.callback_query(F.data.startswith("admin:user:"))
async def admin_user_callback(callback: CallbackQuery, db: Database, config: Config) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    user_id = int(callback.data.split(":")[2])
    await callback.answer()
    await _show_user_card(callback, db, config, user_id)


@admin_router.callback_query(F.data == "admin:subreqs")
async def admin_subscriptions_callback(callback: CallbackQuery, db: Database) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    items = await db.list_subscription_requests()
    await callback.answer()
    await _edit_or_send(
        callback,
        render_subscription_requests(items),
        reply_markup=admin_subscription_requests_kb(items),
    )


@admin_router.callback_query(F.data.startswith("admin:subreq:"))
async def admin_subscription_request_callback(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    parts = callback.data.split(":")
    request_id = int(parts[2])
    item = await db.get_subscription_request(request_id)
    if item is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    if len(parts) == 3:
        await callback.answer()
        await _edit_or_send(
            callback,
            render_subscription_request(item),
            reply_markup=admin_subscription_request_kb(request_id=item["id"], user_id=item["user_id"]),
        )
        return

    action = parts[3]
    if action == "approve":
        days = int(parts[4])
        await db.extend_subscription(item["user_id"], days)
        await db.mark_subscription_request(item["id"], "approved", callback.from_user.id)
        try:
            await bot.send_message(
                item["user_id"],
                f"Твоя заявка одобрена. Premium активирован на <b>{days}</b> дней.",
            )
        except Exception:
            pass
        await callback.answer("Заявка одобрена")
        await _show_user_card(callback, db, config, item["user_id"])
        return

    if action == "reject":
        await db.mark_subscription_request(item["id"], "rejected", callback.from_user.id)
        try:
            await bot.send_message(item["user_id"], "Твоя заявка на Premium была отклонена.")
        except Exception:
            pass
        await callback.answer("Заявка отклонена")
        items = await db.list_subscription_requests()
        await _edit_or_send(
            callback,
            render_subscription_requests(items),
            reply_markup=admin_subscription_requests_kb(items),
        )


@admin_router.callback_query(F.data == "admin:settings")
async def admin_settings_callback(callback: CallbackQuery, db: Database) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    settings = await db.get_settings_map()
    await callback.answer()
    await _edit_or_send(
        callback,
        render_admin_settings(settings),
        reply_markup=admin_settings_kb(settings),
    )


@admin_router.callback_query(F.data.startswith("admin:setting:"))
async def admin_setting_select_callback(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    admin = await _require_admin(callback, db)
    if admin is None:
        return
    key = callback.data.split(":", maxsplit=2)[2]
    settings = await db.get_settings_map()
    current = settings.get(key, "")
    await state.set_state(AdminStates.waiting_for_setting_value)
    await state.update_data(setting_key=key)
    await callback.answer()
    await _edit_or_send(
        callback,
        (
            f"<b>Изменение настройки</b>\n"
            f"Ключ: <code>{key}</code>\n"
            f"Текущее значение:\n<blockquote>{current[:700]}</blockquote>\n"
            "Следующим сообщением отправь новое значение."
        ),
        reply_markup=admin_main_kb(),
    )


@admin_router.message(AdminStates.waiting_for_setting_value)
async def admin_setting_message(
    message: Message,
    state: FSMContext,
    db: Database,
) -> None:
    admin = await _require_admin(message, db)
    if admin is None:
        return
    data = await state.get_data()
    key = data.get("setting_key")
    if not key:
        await state.clear()
        await message.answer("Состояние потеряно. Открой настройки заново.")
        return
    value = (message.text or message.caption or "").strip()
    if not value:
        await message.answer("Отправь новое значение обычным текстом.")
        return
    if key in INT_SETTINGS:
        try:
            if int(value) <= 0:
                raise ValueError
        except ValueError:
            await message.answer("Нужно положительное целое число.")
            return
    if key in FLOAT_SETTINGS:
        try:
            float(value)
        except ValueError:
            await message.answer("Нужно число.")
            return
    await db.update_setting(key, value)
    await state.clear()
    settings = await db.get_settings_map()
    await message.answer(
        "Настройка сохранена.\n\n" + render_admin_settings(settings),
        reply_markup=admin_settings_kb(settings),
    )


@admin_router.message(AdminStates.waiting_for_subscription_days)
async def admin_custom_days_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    admin = await _require_admin(message, db)
    if admin is None:
        return
    raw = (message.text or "").strip()
    try:
        days = int(raw)
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Нужно отправить положительное число дней.")
        return
    data = await state.get_data()
    user_id = data.get("target_user_id")
    if not user_id:
        await state.clear()
        await message.answer("Состояние потеряно. Открой карточку пользователя заново.")
        return
    await db.extend_subscription(int(user_id), days)
    await state.clear()
    try:
        await bot.send_message(int(user_id), f"Тебе выдали Premium на <b>{days}</b> дней.")
    except Exception:
        pass
    await message.answer("Подписка обновлена.")
    await _show_user_card(message, db, config, int(user_id))
