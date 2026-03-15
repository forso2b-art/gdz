from __future__ import annotations

from collections.abc import Iterable

ADMIN_FOREVER_DAYS = 9999
ADMIN_PAGE_SIZE = 8
USER_HISTORY_LIMIT = 5
MODEL_NAME = "openai/gpt-oss-120b"

GRADES = list(range(1, 12))

SUBJECTS_BY_GRADE: dict[int, list[tuple[str, str]]] = {
    1: [
        ("math", "Математика"),
        ("russian", "Русский язык"),
        ("reading", "Литературное чтение"),
        ("world", "Окружающий мир"),
        ("english", "Английский язык"),
    ],
    2: [
        ("math", "Математика"),
        ("russian", "Русский язык"),
        ("reading", "Литературное чтение"),
        ("world", "Окружающий мир"),
        ("english", "Английский язык"),
    ],
    3: [
        ("math", "Математика"),
        ("russian", "Русский язык"),
        ("reading", "Литературное чтение"),
        ("world", "Окружающий мир"),
        ("english", "Английский язык"),
    ],
    4: [
        ("math", "Математика"),
        ("russian", "Русский язык"),
        ("reading", "Литературное чтение"),
        ("world", "Окружающий мир"),
        ("english", "Английский язык"),
    ],
    5: [
        ("math", "Математика"),
        ("russian", "Русский язык"),
        ("literature", "Литература"),
        ("history", "История"),
        ("biology", "Биология"),
        ("geography", "География"),
        ("english", "Английский язык"),
        ("informatics", "Информатика"),
    ],
    6: [
        ("math", "Математика"),
        ("russian", "Русский язык"),
        ("literature", "Литература"),
        ("history", "История"),
        ("biology", "Биология"),
        ("geography", "География"),
        ("english", "Английский язык"),
        ("informatics", "Информатика"),
    ],
    7: [
        ("algebra", "Алгебра"),
        ("geometry", "Геометрия"),
        ("russian", "Русский язык"),
        ("literature", "Литература"),
        ("physics", "Физика"),
        ("biology", "Биология"),
        ("history", "История"),
        ("geography", "География"),
        ("english", "Английский язык"),
        ("informatics", "Информатика"),
    ],
    8: [
        ("algebra", "Алгебра"),
        ("geometry", "Геометрия"),
        ("russian", "Русский язык"),
        ("literature", "Литература"),
        ("physics", "Физика"),
        ("chemistry", "Химия"),
        ("biology", "Биология"),
        ("history", "История"),
        ("social", "Обществознание"),
        ("english", "Английский язык"),
        ("informatics", "Информатика"),
    ],
    9: [
        ("algebra", "Алгебра"),
        ("geometry", "Геометрия"),
        ("russian", "Русский язык"),
        ("literature", "Литература"),
        ("physics", "Физика"),
        ("chemistry", "Химия"),
        ("biology", "Биология"),
        ("history", "История"),
        ("social", "Обществознание"),
        ("english", "Английский язык"),
        ("informatics", "Информатика"),
    ],
    10: [
        ("algebra", "Алгебра"),
        ("geometry", "Геометрия"),
        ("russian", "Русский язык"),
        ("literature", "Литература"),
        ("physics", "Физика"),
        ("chemistry", "Химия"),
        ("biology", "Биология"),
        ("history", "История"),
        ("social", "Обществознание"),
        ("english", "Английский язык"),
        ("informatics", "Информатика"),
    ],
    11: [
        ("algebra", "Алгебра"),
        ("geometry", "Геометрия"),
        ("russian", "Русский язык"),
        ("literature", "Литература"),
        ("physics", "Физика"),
        ("chemistry", "Химия"),
        ("biology", "Биология"),
        ("history", "История"),
        ("social", "Обществознание"),
        ("english", "Английский язык"),
        ("informatics", "Информатика"),
    ],
}

SUBJECT_LABELS = {
    key: label
    for grade_subjects in SUBJECTS_BY_GRADE.values()
    for key, label in grade_subjects
}


def get_subjects_for_grade(grade: int) -> list[tuple[str, str]]:
    return SUBJECTS_BY_GRADE.get(grade, [])


def get_subject_label(subject_key: str) -> str:
    return SUBJECT_LABELS.get(subject_key, subject_key)


def iter_subject_keys() -> Iterable[str]:
    return SUBJECT_LABELS.keys()
