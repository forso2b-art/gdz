from __future__ import annotations

from gdz_bot.constants import MODEL_NAME

DEFAULT_SETTINGS: dict[str, str] = {
    "free_daily_limit": "3",
    "premium_daily_limit": "100",
    "default_premium_days": "30",
    "free_reasoning_effort": "low",
    "premium_reasoning_effort": "high",
    "free_model_name": MODEL_NAME,
    "premium_model_name": MODEL_NAME,
    "free_temperature": "0.35",
    "premium_temperature": "0.2",
    "free_max_tokens": "2200",
    "premium_max_tokens": "4200",
    "premium_pitch_text": (
        "Премиум открывает до 100 решений в день, высокий уровень рассуждений "
        "и более точные, подробные разборы."
    ),
    "free_system_prompt": (
        "Ты помогаешь школьнику быстро получить короткое и понятное решение по заданию. "
        "Пиши только по существу, не добавляй лишнюю теорию, если она не нужна. "
        "Отвечай на русском языке. "
        "Верни строгий JSON без markdown: "
        "{\"summary\": string, \"solution_steps\": [string], \"final_answer\": string, "
        "\"confidence_note\": string}. "
        "Для бесплатного режима делай 2-4 шага, кратко, без длинных проверок."
    ),
    "premium_system_prompt": (
        "Ты сильный ИИ-репетитор по школьным предметам. "
        "Решай задания максимально точно, последовательно и проверяй ответ перед выдачей. "
        "Если условие двусмысленное, коротко обозначь допущение. "
        "Отвечай на русском языке. "
        "Верни строгий JSON без markdown: "
        "{\"summary\": string, \"solution_steps\": [string], \"final_answer\": string, "
        "\"confidence_note\": string}. "
        "Для премиум-режима делай 4-8 шагов, объясняй логику простым языком и добавляй самопроверку."
    ),
}
