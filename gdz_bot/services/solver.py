from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from gdz_bot.config import Config
from gdz_bot.db import Database
from gdz_bot.services.openrouter import OpenRouterClient


@dataclass(slots=True)
class SolveProfile:
    mode: str
    model_name: str
    reasoning_effort: str
    system_prompt: str
    temperature: float
    max_tokens: int


@dataclass(slots=True)
class SolveResult:
    summary: str
    solution_steps: list[str]
    answer: str
    confidence_note: str
    usage: dict[str, int | None]
    raw_response: str
    model_name: str
    reasoning_effort: str
    mode: str


class SolverService:
    def __init__(self, config: Config, db: Database, client: OpenRouterClient) -> None:
        self.config = config
        self.db = db
        self.client = client

    async def get_profile(self, premium: bool) -> SolveProfile:
        settings = await self.db.get_settings_map()
        prefix = "premium" if premium else "free"
        return SolveProfile(
            mode=prefix,
            model_name=settings[f"{prefix}_model_name"],
            reasoning_effort=settings[f"{prefix}_reasoning_effort"],
            system_prompt=settings[f"{prefix}_system_prompt"],
            temperature=float(settings[f"{prefix}_temperature"]),
            max_tokens=int(settings[f"{prefix}_max_tokens"]),
        )

    async def solve_task(self, grade: int, subject_label: str, task_text: str, premium: bool) -> SolveResult:
        profile = await self.get_profile(premium)
        payload = {
            "model": profile.model_name,
            "messages": [
                {"role": "system", "content": profile.system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Реши школьное задание.\n"
                        f"Класс: {grade}\n"
                        f"Предмет: {subject_label}\n"
                        f"Условие задания:\n{task_text}\n\n"
                        "Сформируй короткое описание, понятное решение по шагам и точный ответ."
                    ),
                },
            ],
            "temperature": profile.temperature,
            "max_tokens": profile.max_tokens,
            "reasoning": {"effort": profile.reasoning_effort},
        }
        response = await self.client.create_chat_completion(payload)
        content = self._extract_content(response)
        parsed = self._parse_json(content)
        usage = response.get("usage", {}) if isinstance(response, dict) else {}
        return SolveResult(
            summary=parsed["summary"],
            solution_steps=parsed["solution_steps"],
            answer=parsed["final_answer"],
            confidence_note=parsed["confidence_note"],
            usage={
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
            raw_response=content,
            model_name=profile.model_name,
            reasoning_effort=profile.reasoning_effort,
            mode=profile.mode,
        )

    def _extract_content(self, response: dict[str, Any]) -> str:
        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError("OpenRouter response does not contain choices")
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    chunks.append(str(item.get("text", "")))
            return "\n".join(chunk.strip() for chunk in chunks if chunk.strip())
        return str(content).strip()

    def _parse_json(self, content: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            candidate = match.group(0)
            try:
                data = json.loads(candidate)
                return self._normalize_payload(data)
            except json.JSONDecodeError:
                pass
        return self._normalize_payload(
            {
                "summary": "Краткий разбор сформирован в свободной форме.",
                "solution_steps": [line.strip() for line in content.splitlines() if line.strip()],
                "final_answer": content.splitlines()[-1].strip() if content.splitlines() else "Ответ не найден.",
                "confidence_note": "Модель не вернула JSON, поэтому показан сырой ответ.",
            }
        )

    def _normalize_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        summary = str(data.get("summary") or "Краткое описание не получено.").strip()
        final_answer = str(data.get("final_answer") or data.get("answer") or "Ответ не указан.").strip()
        confidence_note = str(data.get("confidence_note") or "").strip()
        raw_steps = data.get("solution_steps")
        if isinstance(raw_steps, list):
            steps = [str(item).strip() for item in raw_steps if str(item).strip()]
        elif isinstance(raw_steps, str):
            steps = [line.strip("-• \n") for line in raw_steps.splitlines() if line.strip()]
        else:
            steps = []
        if not steps:
            steps = ["Подробные шаги не были выделены моделью."]
        return {
            "summary": summary,
            "solution_steps": steps,
            "final_answer": final_answer,
            "confidence_note": confidence_note or "Решение сгенерировано автоматически и требует быстрой проверки.",
        }
