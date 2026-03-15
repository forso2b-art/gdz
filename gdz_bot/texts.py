from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from gdz_bot.constants import get_subject_label
from gdz_bot.utils import dt_human, html, short


def subscription_is_active(user: dict, timezone: str) -> bool:
    expiry = user.get("subscription_expires_at")
    if not expiry:
        return False
    now = datetime.now(ZoneInfo(timezone))
    return datetime.fromisoformat(expiry) > now


def render_main_menu(
    user: dict,
    *,
    timezone: str,
    daily_limit: int,
    remaining: int,
) -> str:
    premium = subscription_is_active(user, timezone)
    grade = user.get("selected_class")
    subject = user.get("selected_subject")
    subject_label = get_subject_label(subject) if subject else "не выбран"
    status = "Premium" if premium else "Free"
    return (
        "<b>ГДЗ-бот</b>\n"
        f"<blockquote>Тариф: <b>{status}</b>\n"
        f"Лимит сегодня: <b>{remaining}/{daily_limit}</b>\n"
        f"Класс: <b>{grade or 'не выбран'}</b>\n"
        f"Предмет: <b>{html(subject_label)}</b></blockquote>\n"
        "Выбери класс и предмет, затем загрузи текст задания или фото с подписью."
    )


def render_help() -> str:
    return (
        "<b>Как пользоваться</b>\n"
        "<blockquote>"
        "1. Выбери класс.\n"
        "2. Выбери предмет.\n"
        "3. Нажми «Загрузить задание».\n"
        "4. Отправь текст задания или фото/документ с подписью.</blockquote>\n"
        "В ответ бот выдаст <b>краткое описание</b>, <b>понятное решение</b> и <b>готовый ответ</b>."
    )


def render_access(
    user: dict,
    *,
    timezone: str,
    daily_limit: int,
    remaining: int,
    used: int,
) -> str:
    premium = subscription_is_active(user, timezone)
    expires = user.get("subscription_expires_at")
    return (
        "<b>Мой доступ</b>\n"
        f"<blockquote>Статус: <b>{'Premium' if premium else 'Free'}</b>\n"
        f"Сегодня использовано: <b>{used}</b>\n"
        f"Осталось сегодня: <b>{remaining}</b>\n"
        f"Дневной лимит: <b>{daily_limit}</b>\n"
        f"Подписка до: <b>{html(dt_human(expires))}</b></blockquote>"
    )


def render_tariffs(premium_pitch_text: str) -> str:
    return (
        "<b>Тарифы</b>\n"
        "<blockquote>"
        "<b>Free</b>: до 3 запросов в день, краткое решение, low-think.\n"
        "<b>Premium</b>: до 100 запросов в день, более точное и подробное решение, high-think."
        "</blockquote>\n"
        f"{html(premium_pitch_text)}"
    )


def render_solve_prompt(grade: int, subject_label: str) -> str:
    return (
        "<b>Загрузка задания</b>\n"
        f"<blockquote>Класс: <b>{grade}</b>\nПредмет: <b>{html(subject_label)}</b></blockquote>\n"
        "Пришли текст задания одним сообщением. Если отправляешь фото или файл, добавь подпись с условием."
    )


def render_solution(
    *,
    grade: int,
    subject_label: str,
    summary: str,
    solution_steps: list[str],
    answer: str,
    confidence_note: str,
    premium: bool,
) -> str:
    steps_text = "\n".join(
        f"<b>Шаг {index}.</b> {html(step)}" for index, step in enumerate(solution_steps, start=1)
    )
    badge = "Premium" if premium else "Free"
    return (
        f"<b>Решение • {badge}</b>\n"
        f"<blockquote>Класс: <b>{grade}</b>\nПредмет: <b>{html(subject_label)}</b></blockquote>\n"
        f"<b>Кратко:</b>\n{html(summary)}\n\n"
        f"<b>Решение:</b>\n{steps_text}\n\n"
        f"<b>Ответ:</b>\n<code>{html(answer)}</code>\n\n"
        f"<i>{html(confidence_note)}</i>"
    )


def render_history(requests: list[dict]) -> str:
    if not requests:
        return "<b>История</b>\nУ тебя пока нет решенных заданий."
    lines = ["<b>История</b>"]
    for item in requests:
        lines.append(
            f"• <b>#{item['id']}</b> {html(get_subject_label(item['subject_key']))} "
            f"({html(dt_human(item['created_at']))})"
        )
        lines.append(f"  {html(short(item.get('short_description') or item.get('task_text')))}")
    return "\n".join(lines)


def render_request_detail(item: dict) -> str:
    return (
        f"<b>Запрос #{item['id']}</b>\n"
        f"<blockquote>Класс: <b>{item['class_number']}</b>\n"
        f"Предмет: <b>{html(get_subject_label(item['subject_key']))}</b>\n"
        f"Режим: <b>{html(item['quality_mode'])}</b>\n"
        f"Создан: <b>{html(dt_human(item['created_at']))}</b></blockquote>\n"
        f"<b>Условие:</b>\n{html(item['task_text'])}\n\n"
        f"<b>Кратко:</b>\n{html(item.get('short_description') or '—')}\n\n"
        f"<b>Решение:</b>\n{html(item.get('solution_text') or '—')}\n\n"
        f"<b>Ответ:</b>\n<code>{html(item.get('answer_text') or '—')}</code>"
    )


def render_admin_stats(stats: dict[str, int]) -> str:
    return (
        "<b>Статистика</b>\n"
        f"<blockquote>Пользователей: <b>{stats['users_total']}</b>\n"
        f"Премиум: <b>{stats['premium_total']}</b>\n"
        f"Активных сегодня: <b>{stats['active_today']}</b>\n"
        f"Всего запросов: <b>{stats['requests_total']}</b>\n"
        f"Запросов сегодня: <b>{stats['requests_today']}</b>\n"
        f"Заявок в ожидании: <b>{stats['pending_subscriptions']}</b></blockquote>"
    )


def render_admin_user(user: dict, *, timezone: str, daily_limit: int, remaining: int) -> str:
    premium = subscription_is_active(user, timezone)
    username = f"@{user['username']}" if user.get("username") else "нет"
    return (
        f"<b>Пользователь {user['user_id']}</b>\n"
        f"<blockquote>Имя: <b>{html(user['full_name'])}</b>\n"
        f"Username: <b>{html(username)}</b>\n"
        f"Статус: <b>{'Premium' if premium else 'Free'}</b>\n"
        f"Блок: <b>{'да' if user['is_blocked'] else 'нет'}</b>\n"
        f"Лимит сегодня: <b>{remaining}/{daily_limit}</b>\n"
        f"Всего запросов: <b>{user['total_requests']}</b>\n"
        f"Класс: <b>{user.get('selected_class') or 'не выбран'}</b>\n"
        f"Предмет: <b>{html(get_subject_label(user.get('selected_subject')) if user.get('selected_subject') else 'не выбран')}</b>\n"
        f"Подписка до: <b>{html(dt_human(user.get('subscription_expires_at')))}</b></blockquote>"
    )


def render_admin_user_history(user: dict, requests: list[dict]) -> str:
    if not requests:
        return f"<b>История {html(user['full_name'])}</b>\nЗапросов пока нет."
    lines = [f"<b>История {html(user['full_name'])}</b>"]
    for item in requests:
        lines.append(
            f"• <b>#{item['id']}</b> {html(get_subject_label(item['subject_key']))}: "
            f"{html(short(item.get('answer_text') or item.get('short_description') or item['task_text'], 80))}"
        )
    return "\n".join(lines)


def render_admin_settings(settings: dict[str, str]) -> str:
    return (
        "<b>Настройки</b>\n"
        f"<blockquote>Free лимит: <b>{html(settings['free_daily_limit'])}</b>\n"
        f"Premium лимит: <b>{html(settings['premium_daily_limit'])}</b>\n"
        f"Premium дни по умолчанию: <b>{html(settings['default_premium_days'])}</b>\n"
        f"Free think: <b>{html(settings['free_reasoning_effort'])}</b>\n"
        f"Premium think: <b>{html(settings['premium_reasoning_effort'])}</b></blockquote>\n"
        "Нажми на параметр ниже, чтобы изменить его следующим сообщением."
    )


def render_subscription_requests(items: list[dict]) -> str:
    if not items:
        return "<b>Заявки на премиум</b>\nСейчас нет ожидающих заявок."
    lines = ["<b>Заявки на премиум</b>"]
    for item in items:
        lines.append(
            f"• <b>#{item['id']}</b> {html(item['full_name'])} ({html(dt_human(item['created_at']))})"
        )
    return "\n".join(lines)


def render_subscription_request(item: dict) -> str:
    username = f"@{item['username']}" if item.get("username") else "нет"
    note = item.get("note") or "без комментария"
    return (
        f"<b>Заявка #{item['id']}</b>\n"
        f"<blockquote>Пользователь: <b>{html(item['full_name'])}</b>\n"
        f"Username: <b>{html(username)}</b>\n"
        f"Статус: <b>{html(item['status'])}</b>\n"
        f"Создана: <b>{html(dt_human(item['created_at']))}</b></blockquote>\n"
        f"<b>Комментарий:</b>\n{html(note)}"
    )
