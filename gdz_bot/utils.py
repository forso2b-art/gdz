from __future__ import annotations

from datetime import datetime
from html import escape

from aiogram.types import CallbackQuery, Message


def html(text: str | None) -> str:
    return escape(text or "")


def dt_human(value: str | None) -> str:
    if not value:
        return "не задано"
    return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M")


def short(text: str | None, limit: int = 140) -> str:
    if not text:
        return "—"
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


async def smart_reply(event: Message | CallbackQuery, text: str, **kwargs):
    if isinstance(event, CallbackQuery):
        if event.message:
            return await event.message.edit_text(text, **kwargs)
        return await event.answer(text, show_alert=True)
    return await event.answer(text, **kwargs)
