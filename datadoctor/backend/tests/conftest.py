import os
import sys
import tempfile
from pathlib import Path

# Isolated storage per test run; AI off unless a test enables it explicitly.
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="datadoctor-test-")
os.environ["GROQ_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.middleware.ratelimit import limiter  # noqa: E402


@pytest.fixture
def client():
    limiter.reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def other_client():
    """A second browser with its own workspace cookie."""
    with TestClient(app) as c:
        yield c
