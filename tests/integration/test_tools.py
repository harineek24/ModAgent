"""Tests for the policy_lookup/clause_lookup tools and the gather_tool_context
tool-calling round-trip. The raw Groq client is stubbed since these tests
target the local lookup functions and the tool-call loop wiring, not actual
LLM reasoning quality.
"""

import json

from backend.debate.tools import clause_lookup, gather_tool_context, policy_lookup
from backend.models.category import Category


def test_policy_lookup_returns_severity_rubric_and_examples(policy_table):
    expected = policy_table[Category.HATE_SPEECH]
    result = policy_lookup("hate_speech")

    assert result["severity"] == expected.severity.value
    assert result["rubric"] == expected.rubric
    assert result["examples"] == expected.examples
    assert result["debatable"] == expected.debatable


def test_clause_lookup_matches_rubric_text(policy_table):
    rubric = policy_table[Category.HATE_SPEECH].rubric
    query = rubric.split()[0]

    result = clause_lookup("hate_speech", query)

    assert result["matches"][0] == rubric


def test_clause_lookup_falls_back_to_rubric_when_nothing_matches(policy_table):
    rubric = policy_table[Category.HATE_SPEECH].rubric

    result = clause_lookup("hate_speech", "zzz_no_such_text_zzz")

    assert result["matches"] == [rubric]


class StubMessage:
    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls


class StubToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id

        class _Function:
            pass

        self.function = _Function()
        self.function.name = name
        self.function.arguments = json.dumps(arguments)


class StubRawClient:
    """Stub raw Groq client that returns a scripted sequence of responses,
    one per call to chat.completions.create().
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

        class _Completions:
            def create(_self, **kwargs):
                response = self._responses[self.calls]
                self.calls += 1
                return response

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


class StubResponse:
    def __init__(self, message):
        class _Choice:
            pass

        choice = _Choice()
        choice.message = message
        self.choices = [choice]


def test_gather_tool_context_returns_empty_string_when_no_tools_called():
    client = StubRawClient([StubResponse(StubMessage(tool_calls=None))])

    context = gather_tool_context(client, "model", "system prompt", "user message")

    assert context == ""
    assert client.calls == 1


def test_gather_tool_context_executes_tool_call_and_summarizes_result():
    tool_call = StubToolCall("call-1", "policy_lookup", {"category": "hate_speech"})
    client = StubRawClient(
        [
            StubResponse(StubMessage(tool_calls=[tool_call])),
            StubResponse(StubMessage(tool_calls=None)),
        ]
    )

    context = gather_tool_context(client, "model", "system prompt", "user message")

    assert "policy_lookup" in context
    assert client.calls == 2


def test_gather_tool_context_stops_after_max_rounds():
    tool_call = StubToolCall("call-1", "policy_lookup", {"category": "hate_speech"})
    client = StubRawClient(
        [
            StubResponse(StubMessage(tool_calls=[tool_call])),
            StubResponse(StubMessage(tool_calls=[tool_call])),
            StubResponse(StubMessage(tool_calls=[tool_call])),
        ]
    )

    gather_tool_context(client, "model", "system prompt", "user message")

    assert client.calls == 2
