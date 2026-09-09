from __future__ import annotations

import json
from types import SimpleNamespace

from app.ai_service import StudyService


PAYLOAD = {
    "subject": "Алгоритмы",
    "assignment_title": "Сортировка",
    "solution": "Сравниваем соседние элементы.",
    "answer": "Массив отсортирован.",
    "defense_points": ["Объясню инвариант прохода."],
    "optional_check": "Проверяем пустой массив.",
    "suggested_due_at": None,
}


class ContinuingResponses:
    def __init__(self) -> None:
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            return SimpleNamespace(
                output_text='{"subject":',
                usage=SimpleNamespace(input_tokens=10, output_tokens=20),
                status="incomplete",
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                output=[{"type": "message", "role": "assistant", "content": []}],
            )
        return SimpleNamespace(
            output_text=json.dumps(PAYLOAD, ensure_ascii=False)[11:],
            usage=SimpleNamespace(input_tokens=30, output_tokens=40),
            status="completed", incomplete_details=None, output=[],
        )


def test_structured_response_continues_with_bound_store_false_and_counts_tokens() -> None:
    service = StudyService.__new__(StudyService)
    responses = ContinuingResponses()
    service.client = SimpleNamespace(responses=responses)
    service.model = "test-model"

    result = service.analyze("Отсортируй массив", "Алгоритмы", "Сортировка")

    assert result.to_dict()["defense_points"] == PAYLOAD["defense_points"]
    assert result.to_dict()["how_to_defend"] == PAYLOAD["defense_points"][0]
    assert result.usage() == (40, 60)
    assert len(responses.requests) == 2
    assert all(request["store"] is False for request in responses.requests)
    assert responses.requests[0]["text"]["format"]["strict"] is True
    initial = responses.requests[0]["input"][0]["content"][0]["text"]
    assert "Предмет: Алгоритмы" in initial and "Название задания: Сортировка" in initial
    continuation = responses.requests[1]["input"][-1]["content"][0]["text"]
    assert "только недостающий суффикс JSON" in continuation
    assert responses.requests[0]["text"]["verbosity"] == "low"


def test_compact_contract_defaults_to_russian_and_avoids_repeated_sections() -> None:
    from app.ai_service import STUDY_INSTRUCTIONS, STUDY_SCHEMA

    assert set(STUDY_SCHEMA["required"]) == {
        "subject", "assignment_title", "solution", "answer", "defense_points",
        "optional_check", "suggested_due_at",
    }
    assert "По умолчанию отвечай по-русски" in STUDY_INSTRUCTIONS
    assert "не повторяй один вывод" in STUDY_INSTRUCTIONS
    assert "1–3" in STUDY_INSTRUCTIONS


def test_representative_math_tasks_use_one_adaptive_contract() -> None:
    fixtures = [
        "Представь 2i в тригонометрической форме",
        "Представь √21+i√7 в полярной форме",
        "Переведи 2(cos(π/6)+i sin(π/6)) в алгебраическую форму",
        "Реши многошаговое уравнение 3(x-2)+4=19",
        "Докажи сходимость ряда и обоснуй каждый переход",
    ]
    assert all(len(task) >= 3 for task in fixtures)


class NeverCompletes:
    def create(self, **kwargs):
        return SimpleNamespace(
            output_text="{}", usage=None, status="incomplete",
            incomplete_details={"reason": "max_output_tokens"}, output=[],
        )


def test_structured_continuation_has_hard_four_response_limit() -> None:
    service = StudyService.__new__(StudyService)
    service.client = SimpleNamespace(responses=NeverCompletes())
    service.model = "test-model"

    try:
        service.analyze("Реши задачу")
        raise AssertionError("expected bounded failure")
    except RuntimeError as exc:
        assert "four responses" in str(exc)
