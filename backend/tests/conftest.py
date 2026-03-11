import os
import tempfile
import pytest


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary 'repository' directory for testing."""
    return tmp_path


@pytest.fixture
def py_file(tmp_repo):
    """Helper to create a Python file in the temp repo."""
    def _create(filename: str, content: str) -> str:
        fpath = os.path.join(tmp_repo, filename)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w") as f:
            f.write(content)
        return fpath
    return _create