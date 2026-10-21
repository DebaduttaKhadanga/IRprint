from pathlib import Path

import pytest

from irprint.compiler_wrapper import find_tool

FIXTURES = Path(__file__).parent / "fixtures"

requires_clang = pytest.mark.skipif(find_tool("clang") is None, reason="clang not installed")
requires_rustc = pytest.mark.skipif(find_tool("rustc") is None, reason="rustc not installed")


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES
