"""Override the global llm_mock autouse fixture for these pure-function tests.

The repo's tests/conftest.py wires an autouse fixture that depends on
pytest-mock's `mocker`, which is not always installed. These tests don't
touch any LLM, so we replace it with a no-op.
"""
import pytest


@pytest.fixture(scope="function", autouse=True)
def llm_mock():  # noqa: D401
    yield
