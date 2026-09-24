import json

import pytest

from app.assistant import (
    AssistantRequest,
    AssistantStatus,
    ProviderFailure,
    ProviderTimeout,
    QuestionId,
    ask,
)
from app.models import Snapshot
from app.planning import run_plan


def fake(reply: dict[str, object]):  # type: ignore[no-untyped-def]
    seen: dict[str, str] = {}

    def provider(system: str, user: str) -> str:
        seen["user"] = user
        return json.dumps(reply)

    return provider, seen


def _ask(snapshot: Snapshot, qid: QuestionId, provider, text: str | None = None):  # type: ignore[no-untyped-def]
    return ask(
        AssistantRequest(question_id=qid, text=text), run_plan(snapshot), snapshot, provider, "m"
    )


def test_grounded_answer_cites_real_ids_and_plan_numbers(baseline: Snapshot) -> None:
    provider, seen = fake(
        {
            "status": "answered",
            "answer": "C02 is 10 t short because Segment A arrived at 90 t against 101.7 t "
            "planned. C08 is 30 t short: only 20 t of the 500 t station line was left.",
            "citations": ["C02", "C08", "A"],
        }
    )
    result = _ask(baseline, QuestionId.AT_RISK, provider)
    assert result.status is AssistantStatus.ANSWERED
    assert set(result.citations) == {"C02", "C08", "Segment A"}
    # Minimal context: only at-risk clients are sent, never the complete ones or raw farms.
    assert '"C02"' in seen["user"] and '"C01"' not in seen["user"] and '"F01"' not in seen["user"]


@pytest.mark.parametrize(
    ("answer", "why"),
    [
        ("C99 is short by 10 t.", "C99"),  # unknown ID
        ("C02 is short by 12 t.", "12"),  # number the engine never produced
    ],
)
def test_ungrounded_output_is_rejected_not_shown(baseline: Snapshot, answer: str, why: str) -> None:
    provider, _ = fake({"status": "answered", "answer": answer, "citations": ["C02"]})
    result = _ask(baseline, QuestionId.AT_RISK, provider)
    assert result.status is AssistantStatus.INVALID_OUTPUT
    assert result.answer is None and why in (result.notice or "")
    assert result.deterministic_summary  # labelled fallback still available


def test_unsupported_question_is_reported_unavailable(baseline: Snapshot) -> None:
    provider, _ = fake(
        {"status": "unavailable", "answer": "Weather is not in today's plan.", "citations": []}
    )
    result = _ask(baseline, QuestionId.CUSTOM, provider, "Will it rain tomorrow?")
    assert result.status is AssistantStatus.UNAVAILABLE
    assert result.deterministic_summary is None


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ProviderTimeout(), AssistantStatus.TIMEOUT),
        (ProviderFailure("The API key was rejected."), AssistantStatus.PROVIDER_ERROR),
    ],
)
def test_provider_failure_is_honest(
    baseline: Snapshot, error: Exception, status: AssistantStatus
) -> None:
    def provider(system: str, user: str) -> str:
        raise error

    result = _ask(baseline, QuestionId.LOCAL, provider)
    assert result.status is status and result.answer is None
    assert "No AI answer" in (result.notice or "")


def test_no_key_returns_labelled_deterministic_summary(baseline: Snapshot) -> None:
    result = _ask(baseline, QuestionId.LOCAL, None)
    assert result.status is AssistantStatus.NO_KEY and result.answer is None
    assert "60 t" in (result.deterministic_summary or "")
    assert {"F16", "F20", "Segment D"} <= set(result.deterministic_citations)
