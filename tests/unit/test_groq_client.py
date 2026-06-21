import pytest

from backend.clients.groq_client import get_instructor_client
from backend.exceptions import ModAgentError


def test_missing_api_key_raises():
    with pytest.raises(ModAgentError, match="No Groq API key provided"):
        get_instructor_client(api_key=None)


def test_non_ascii_api_key_raises_clear_error():
    with pytest.raises(ModAgentError, match="non-ASCII characters"):
        get_instructor_client(api_key="sk-test’key")


def test_api_key_with_surrounding_whitespace_is_stripped():
    client = get_instructor_client(api_key="  sk-test-key  ")
    assert client is not None
