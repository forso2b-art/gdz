from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from aiogram import F, Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from gdz_bot.config import Config
from gdz_bot.constants import get_subject_label, get_subjects_for_grade
from gdz_bot.db import Database
from gdz_bot.keyboards import (
    access_kb,
    grades_kb,
    history_kb,
    main_menu_kb,
    request_detail_kb,
    result_kb,
    solve_prompt_kb,
    subjects_kb,
    tariffs_kb,
)
from gdz_bot.services.solver import SolverService
from gdz_bot.states import SolveStates
from gdz_bot.texts import (
    render_access,
    render_help,
    render_history,
    render_main_menu,
    render_request_detail,
    render_solution,
    render_solve_prompt,
    render_tariffs,
    render_subscription_request,
    subscription_is_active,
)

logger = logging.getLogger(__name__)

user_router = Router(name="user")


@dataclass(slots=True)
class UserContext:
    user: dict[str, Any]
    settings: dict[str, str]
    premium: bool
    daily_limit: int
    remaining: int
    used: int


async def _edit_or_send(target: Message | CallbackQuery, text: str, **kwargs):
    if isinstance(target, CallbackQuery) and target.message:
        try:
            return await target.message.edit_text(text, **kwargs)
        except TelegramBadRequest:
            return await target.message.answer(text, **kwargs)
    if isinstance(target, CallbackQuery):
        return await target.answer(text, show_alert=True)
    return await target.answer(text, **kwargs)


def _build_user_context(user: dict[str, Any], settings: dict[str, str], config: Config) -> UserContext:
    premium = subscription_is_active(user, config.timezone)
    daily_limit = int(settings["premium_daily_limit" if premium else "free_daily_limit"])
    used = int(user["daily_requests"])
    remaining = max(daily_limit - used, 0)
    return UserContext(
        user=user,
        settings=settings,
        premium=premium,
        daily_limit=daily_limit,
        remaining=remaining,
        used=used,
    )


async def _load_context(tg_user, db: Database, config: Config) -> UserContext:
    user = await db.upsert_user(tg_user)
    settings = await db.get_settings_map()
    return _build_user_context(user, settings, config)


def _extract_task_payload(message: Message) -> tuple[str, str | None, str | None]:
    file_id = None
    file_type = None
    text = (message.text or message.caption or "").strip()
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    return text, file_id, file_type


async def _show_main_menu(target: Message | CallbackQuery, db: Database, config: Config) -> None:
    context = await _load_context(target.from_user, db, config)
    text = render_main_menu(
        context.user,
        timezone=config.timezone,
        daily_limit=context.daily_limit,
        remaining=context.remaining,
    )
    markup = main_menu_kb(
        is_admin=bool(context.user["is_admin"]),
        has_selection=bool(context.user.get("selected_class") and context.user.get("selected_subject")),
        has_class=bool(context.user.get("selected_class")),
    )
    await _edit_or_send(target, text, reply_markup=markup)


async def _show_access_screen(target: Message | CallbackQuery, db: Database, config: Config) -> None:
    context = await _load_context(target.from_user, db, config)
    pending = await db.has_pending_subscription_request(context.user["user_id"])
    await _edit_or_send(
        target,
        render_access(
            context.user,
            timezone=config.timezone,
            daily_limit=context.daily_limit,
            remaining=context.remaining,
            used=context.used,
        ),
        reply_markup=access_kb(is_premium=context.premium, has_pending_request=pending),
    )


async def _notify_admins_about_subscription_request(
    bot: Bot,
    config: Config,
    db: Database,
    request_id: int,
) -> None:
    item = await db.get_subscription_request(request_id)
    if item is None:
        return
    from gdz_bot.keyboards import admin_subscription_request_kb

    text = render_subscription_request(item)
    markup = admin_subscription_request_kb(request_id=item["id"], user_id=item["user_id"])
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception:
            logger.exception("Failed to notify admin %s about subscription request", admin_id)


@user_router.message(CommandStart())
async def start_handler(message: Message, db: Database, config: Config, state: FSMContext) -> None:
    await state.clear()
    await _show_main_menu(message, db, config)


@user_router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


@user_router.callback_query(F.data == "menu:home")
async def main_menu_callback(callback: CallbackQuery, db: Database, config: Config, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _show_main_menu(callback, db, config)


@user_router.callback_query(F.data == "menu:help")
async def help_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await _edit_or_send(callback, render_help(), reply_markup=solve_prompt_kb())


@user_router.callback_query(F.data == "menu:class")
async def class_menu_callback(callback: CallbackQuery, db: Database, config: Config) -> None:
    context = await _load_context(callback.from_user, db, config)
    await callback.answer()
    await _edit_or_send(
        callback,
        "<b>Выбери класс</b>\nНажми на нужный класс ниже.",
        reply_markup=grades_kb(selected_grade=context.user.get("selected_class")),
    )


@user_router.callback_query(F.data.startswith("grade:"))
async def grade_selected_callback(
    callback: CallbackQuery,
    db: Database,
) -> None:
    grade = int(callback.data.split(":")[1])
    await db.upsert_user(callback.from_user)
    await db.save_grade(callback.from_user.id, grade)
    await callback.answer("Класс сохранен")
    await _edit_or_send(
        callback,
        f"<b>{grade} класс</b>\nТеперь выбери предмет.",
        reply_markup=subjects_kb(grade),
    )


@user_router.callback_query(F.data == "menu:subject")
async def subject_menu_callback(callback: CallbackQuery, db: Database, config: Config) -> None:
    context = await _load_context(callback.from_user, db, config)
    grade = context.user.get("selected_class")
    if not grade:
        await callback.answer("Сначала выбери класс", show_alert=True)
        return
    await callback.answer()
    await _edit_or_send(
        callback,
        f"<b>{grade} класс</b>\nВыбери предмет.",
        reply_markup=subjects_kb(grade, selected_subject=context.user.get("selected_subject")),
    )


@user_router.callback_query(F.data.startswith("subject:"))
async def subject_selected_callback(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    _, grade_raw, subject_key = callback.data.split(":", maxsplit=2)
    grade = int(grade_raw)
    allowed_subjects = {key for key, _ in get_subjects_for_grade(grade)}
    if subject_key not in allowed_subjects:
        await callback.answer("Неверный предмет", show_alert=True)
        return
    await db.upsert_user(callback.from_user)
    await db.save_grade(callback.from_user.id, grade)
    await db.save_subject(callback.from_user.id, subject_key)
    await state.set_state(SolveStates.waiting_for_task)
    await callback.answer("Предмет сохранен")
    await _edit_or_send(
        callback,
        render_solve_prompt(grade, get_subject_label(subject_key)),
        reply_markup=solve_prompt_kb(),
    )


@user_router.callback_query(F.data == "menu:solve")
async def solve_menu_callback(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    config: Config,
) -> None:
    context = await _load_context(callback.from_user, db, config)
    grade = context.user.get("selected_class")
    subject_key = context.user.get("selected_subject")
    if not grade or not subject_key:
        await callback.answer("Сначала выбери класс и предмет", show_alert=True)
        return
    await state.set_state(SolveStates.waiting_for_task)
    await callback.answer()
    await _edit_or_send(
        callback,
        render_solve_prompt(grade, get_subject_label(subject_key)),
        reply_markup=solve_prompt_kb(),
    )


@user_router.callback_query(F.data == "menu:access")
async def access_callback(callback: CallbackQuery, db: Database, config: Config) -> None:
    await callback.answer()
    await _show_access_screen(callback, db, config)


@user_router.callback_query(F.data == "menu:tariffs")
async def tariffs_callback(callback: CallbackQuery, db: Database, config: Config) -> None:
    context = await _load_context(callback.from_user, db, config)
    pending = await db.has_pending_subscription_request(context.user["user_id"])
    await callback.answer()
    await _edit_or_send(
        callback,
        render_tariffs(context.settings["premium_pitch_text"]),
        reply_markup=tariffs_kb(is_premium=context.premium, has_pending_request=pending),
    )


@user_router.callback_query(F.data == "premium:request")
async def premium_request_callback(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    config: Config,
) -> None:
    context = await _load_context(callback.from_user, db, config)
    if context.premium:
        await callback.answer("У тебя уже активен Premium", show_alert=True)
        return
    if context.user["is_blocked"]:
        await callback.answer("Твой аккаунт заблокирован", show_alert=True)
        return
    request_id = await db.create_subscription_request(context.user["user_id"])
    if request_id is None:
        await callback.answer("Заявка уже ожидает обработки", show_alert=True)
        return
    await _notify_admins_about_subscription_request(bot, config, db, request_id)
    await callback.answer("Заявка отправлена администратору", show_alert=True)
    await _show_access_screen(callback, db, config)


@user_router.callback_query(F.data == "menu:history")
async def history_callback(callback: CallbackQuery, db: Database) -> None:
    await db.upsert_user(callback.from_user)
    requests = await db.list_recent_requests(callback.from_user.id)
    await callback.answer()
    await _edit_or_send(callback, render_history(requests), reply_markup=history_kb(requests))


@user_router.callback_query(F.data.startswith("req:"))
async def request_detail_callback(callback: CallbackQuery, db: Database) -> None:
    await db.upsert_user(callback.from_user)
    request_id = int(callback.data.split(":")[1])
    item = await db.get_request(request_id)
    if item is None:
        await callback.answer("Запрос не найден", show_alert=True)
        return
    user = await db.get_user(callback.from_user.id)
    is_admin = bool(user and user["is_admin"])
    if item["user_id"] != callback.from_user.id and not is_admin:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.answer()
    await _edit_or_send(
        callback,
        render_request_detail(item),
        reply_markup=request_detail_kb(is_admin=is_admin, user_id=item["user_id"]),
    )


@user_router.message(SolveStates.waiting_for_task)
async def solve_task_message(
    message: Message,
    state: FSMContext,
    db: Database,
    config: Config,
    solver: SolverService,
) -> None:
    context = await _load_context(message.from_user, db, config)
    if context.user["is_blocked"]:
        await state.clear()
        await message.answer("Твой аккаунт заблокирован. Для уточнения статуса напиши администратору.")
        return

    grade = context.user.get("selected_class")
    subject_key = context.user.get("selected_subject")
    if not grade or not subject_key:
        await state.clear()
        await message.answer("Сначала выбери класс и предмет через меню.")
        return

    task_text, file_id, file_type = _extract_task_payload(message)
    if not task_text:
        await message.answer(
            "Пришли текст задания. Если отправляешь фото или файл, добавь подпись с условием."
        )
        return
    if len(task_text) < 5:
        await message.answer("Условие слишком короткое. Пришли задание подробнее.")
        return

    allowed, _, _ = await db.reserve_quota(context.user["user_id"], context.daily_limit)
    if not allowed:
        await message.answer(
            "Лимит на сегодня исчерпан. Открой раздел «Тарифы» и отправь заявку на Premium."
        )
        return

    profile = await solver.get_profile(context.premium)
    request_id = await db.create_request(
        user_id=context.user["user_id"],
        class_number=grade,
        subject_key=subject_key,
        task_text=task_text,
        quality_mode=profile.mode,
        reasoning_effort=profile.reasoning_effort,
        model_name=profile.model_name,
        task_file_id=file_id,
        task_file_type=file_type,
    )

    progress = await message.answer("Решаю задачу. Это может занять до пары минут.")
    try:
        result = await solver.solve_task(
            grade=grade,
            subject_label=get_subject_label(subject_key),
            task_text=task_text,
            premium=context.premium,
        )
    except Exception as exc:
        logger.exception("Failed to solve task")
        await db.fail_request(request_id, str(exc))
        await db.release_quota(context.user["user_id"])
        await state.clear()
        await progress.edit_text(
            "Не удалось получить ответ от модели. Запрос не был засчитан, попробуй еще раз позже.",
            reply_markup=solve_prompt_kb(),
        )
        return

    await db.complete_request(
        request_id,
        summary=result.summary,
        solution="\n".join(result.solution_steps),
        answer=result.answer,
        confidence_note=result.confidence_note,
        usage=result.usage,
    )
    await state.clear()
    await progress.edit_text(
        render_solution(
            grade=grade,
            subject_label=get_subject_label(subject_key),
            summary=result.summary,
            solution_steps=result.solution_steps,
            answer=result.answer,
            confidence_note=result.confidence_note,
            premium=context.premium,
        ),
        reply_markup=result_kb(),
    )


@user_router.message()
async def fallback_message(message: Message, db: Database, config: Config) -> None:
    await _show_main_menu(message, db, config)
