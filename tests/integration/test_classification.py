"""Tests for the classifier <-> Instructor/Groq boundary. No live network calls --
the Instructor client is replaced with a stub that mimics its retry/validation
contract so we can assert behavior without hitting Groq.
"""

import pytest

from backend.classification.classifier import classify
from backend.exceptions import ClassificationError
from backend.models.category import Category
from backend.models.classification import ClassificationResult


class StubInstructorClient:
    """Mimics instructor.Instructor's chat.completions.create surface, returning
    queued responses/exceptions in order to simulate retry sequences."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0

        class _Completions:
            def create(_self, **kwargs):
                self.call_count += 1
                response = self._responses.pop(0)
                if isinstance(response, Exception):
                    raise response
                return response

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def _valid_result(score=0.9):
    scores = {c: 0.0 for c in Category}
    scores[Category.HATE_SPEECH] = score
    return ClassificationResult(scores=scores, detected_language="en", flags=[])


def test_valid_response_parses_into_typed_result():
    client = StubInstructorClient([_valid_result()])
    result = classify(client, "some content")
    assert isinstance(result, ClassificationResult)
    assert result.scores[Category.HATE_SPEECH] == 0.9


def test_transport_error_raises_classification_error():
    client = StubInstructorClient([ConnectionError("timeout")])
    with pytest.raises(ClassificationError):
        classify(client, "some content")


def test_exhausted_retries_raises_classification_error():
    client = StubInstructorClient([ValueError("bad json"), ValueError("bad json")])
    with pytest.raises(ClassificationError):
        classify(client, "some content")


def test_non_english_content_produces_valid_result():
    scores = {c: 0.0 for c in Category}
    result_in = ClassificationResult(scores=scores, detected_language="es", flags=[])
    client = StubInstructorClient([result_in])
    result = classify(client, "contenido en espanol")
    assert result.detected_language == "es"


def test_low_confidence_flag_passes_through_unmodified():
    scores = {c: 0.0 for c in Category}
    result_in = ClassificationResult(scores=scores, detected_language="en", flags=["low_confidence_input"])
    client = StubInstructorClient([result_in])
    result = classify(client, "ambiguous content")
    assert result.flags == ["low_confidence_input"]


def test_call_count_recorded_for_successful_first_attempt():
    client = StubInstructorClient([_valid_result()])
    classify(client, "some content")
    assert client.call_count == 1
