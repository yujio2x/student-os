from __future__ import annotations

import json
from types import SimpleNamespace

from app.ai_service import StudyService


PAYLOAD = {
    "subject": "Алгоритмы",
    "assignment_title": "Сортировка",
    "analysis": "Нужно понять условие",
    "explanation": "Полное решение",
    "approach": ["Шаг 1"],
    "checks": ["Граничный случай"],
    "how_to_defend": "Я объясню основную идею",
    "defense_questions": ["Почему этот подход?"],
    "pitfalls": ["Не объяснить шаг"],
    "suggested_due_at": None,
}


class ContinuingResponses:
    def __init__(self) -> None:
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            return SimpleNamespace(
                output_text='{"subject":"оборвано',
                usage=SimpleNamespace(input_tokens=10, output_tokens=20),
                status="incomplete",
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
                output=[{"type": "message", "role": "assistant", "content": []}],
            )
        return SimpleNamespace(
            output_text=json.dumps(PAYLOAD, ensure_ascii=False),
            usage=SimpleNamespace(input_tokens=30, output_tokens=40),
            status="completed", incomplete_details=None, output=[],
        )


def test_structured_response_continues_with_bound_store_false_and_counts_tokens() -> None:
    service = StudyService.__new__(StudyService)
    responses = ContinuingResponses()
    service.client = SimpleNamespace(responses=responses)
    service.model = "test-model"

    result = service.analyze("Отсортируй массив", "Алгоритмы", "Сортировка")

    assert result.to_dict()["how_to_defend"] == PAYLOAD["how_to_defend"]
    assert result.usage() == (40, 60)
    assert len(responses.requests) == 2
    assert all(request["store"] is False for request in responses.requests)
    assert responses.requests[0]["text"]["format"]["strict"] is True
    initial = responses.requests[0]["input"][0]["content"][0]["text"]
    assert "Предмет: Алгоритмы" in initial and "Название задания: Сортировка" in initial
    continuation = responses.requests[1]["input"][-1]["content"][0]["text"]
    assert "полный валидный JSON-объект" in continuation


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
