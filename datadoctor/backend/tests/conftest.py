import os
import sys
import tempfile
from pathlib import Path

# Isolated storage per test run; AI off unless a test enables it explicitly.
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="datadoctor-test-")
os.environ["GROQ_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
