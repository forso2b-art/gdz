from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from gdz_bot.config import load_config
from gdz_bot.db import Database
from gdz_bot.handlers.admin import admin_router
from gdz_bot.handlers.user import user_router
from gdz_bot.services.openrouter import OpenRouterClient
from gdz_bot.services.solver import SolverService


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    config = load_config()

    db = Database(config)
    await db.connect()
    await db.init_schema()

    openrouter = OpenRouterClient(config)
    solver = SolverService(config=config, db=db, client=openrouter)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["config"] = config
    dp["db"] = db
    dp["solver"] = solver
    dp.include_router(admin_router)
    dp.include_router(user_router)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await openrouter.close()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
