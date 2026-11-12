import pytest

from app.config import settings
from app.services.storage.paths import UnsafePathError, remove, safe_path


@pytest.mark.parametrize("name", ["../etc/passwd", "..", "a/../../b", "/abs", "", ".hidden", "a\\b", "x" * 200])
def test_safe_path_rejects_traversal_and_odd_names(name):
    with pytest.raises(UnsafePathError):
        safe_path("originals", name)


def test_safe_path_rejects_unknown_area():
    with pytest.raises(UnsafePathError):
        safe_path("../", "file.csv")


def test_safe_path_accepts_generated_names():
    p = safe_path("originals", "3f2b0c1e-0000-4000-8000-000000000000.xlsx")
    assert p.parent == (settings.storage_dir / "originals").resolve()


def test_remove_refuses_paths_outside_storage(tmp_path):
    outside = tmp_path / "keep.txt"
    outside.write_text("x")
    with pytest.raises(UnsafePathError):
        remove(outside)
    assert outside.exists()
