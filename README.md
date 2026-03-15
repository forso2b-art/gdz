# GDZ Telegram Bot

Telegram-бот на `aiogram 3.26.0` с `SQLite`, inline UX и решением школьных задач через `OpenRouter` + `openai/gpt-oss-120b`.

## Что умеет

- Выбор класса и предмета через inline-кнопки
- Прием задания текстом или фото/файлом с подписью
- Ответ в HTML-формате: краткое описание, решение по шагам и готовый ответ
- Ротация пяти OpenRouter API-ключей по кругу с fallback на следующий ключ при ошибках и лимитах
- Лимиты доступа:
  - `Free`: 3 запроса в день, `low` reasoning, упрощенный системный промпт
  - `Premium`: 100 запросов в день, `high` reasoning, расширенный системный промпт
- Админ-панель для `8753690478`
- Управление пользователями:
  - выдача подписки
  - вечная подписка `9999` дней
  - сброс лимитов
  - блокировка
  - просмотр истории запросов
- Заявки на Premium
- Настройки лимитов и промптов прямо из Telegram

## Важно про "HTML-шрифты"

Telegram Bot API не поддерживает произвольные веб-шрифты. В проекте используется `HTML parse mode`: `<b>`, `<i>`, `<code>`, `<blockquote>` и другие поддерживаемые теги Telegram.

## Запуск

1. Создай `.env` по примеру `.env.example`
2. Заполни переменные:
   - `BOT_TOKEN`
   - `OPENROUTER_API_1` ... `OPENROUTER_API_5`
   - при необходимости `ADMIN_IDS`, `BOT_TIMEZONE`, `SQLITE_PATH`
3. Установи зависимости:

```bash
python -m pip install -r requirements.txt
```

4. Запусти бота:

```bash
python main.py
```

## Переменные окружения

Смотри [.env.example](/C:/gdz/.env.example).

## Структура

- [main.py](/C:/gdz/main.py) — точка входа
- [gdz_bot/db.py](/C:/gdz/gdz_bot/db.py) — SQLite и бизнес-данные
- [gdz_bot/handlers/user.py](/C:/gdz/gdz_bot/handlers/user.py) — пользовательский UX
- [gdz_bot/handlers/admin.py](/C:/gdz/gdz_bot/handlers/admin.py) — админ-панель
- [gdz_bot/services/openrouter.py](/C:/gdz/gdz_bot/services/openrouter.py) — клиент OpenRouter
- [gdz_bot/services/solver.py](/C:/gdz/gdz_bot/services/solver.py) — профили решения free/premium
