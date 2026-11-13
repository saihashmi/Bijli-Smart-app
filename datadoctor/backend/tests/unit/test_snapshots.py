"""Snapshot cache: frames are shared between request threads, so their lookups must be ready before sharing."""

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from app.services.storage import snapshots


def test_cached_frame_is_safe_for_concurrent_lookups():
    # Non-contiguous index, as left behind by removing rows.
    index = [i for i in range(60_000) if i % 3]
    df = pd.DataFrame({"a": range(len(index)), "b": ["x"] * len(index)}, index=index)
    labels = index[:: len(index) // 200]

    def lookups(frame: pd.DataFrame) -> int:
        return sum(1 for label in labels if label in frame.index and frame.at[label, "a"] >= 0)

    for attempt in range(15):
        snapshots.write(df, {}, "ds-threads", f"s{attempt}", 1)
        snapshots.forget()
        with ThreadPoolExecutor(8) as pool:
            frames = list(pool.map(snapshots.load, ["ds-threads"] * 8, [f"s{attempt}"] * 8, [1] * 8))
            results = list(pool.map(lookups, frames))
        assert results == [len(labels)] * 8


def test_load_warms_lookup_tables():
    df = pd.DataFrame({"a": [1, 2, 3]}, index=[0, 2, 5])
    snapshots.write(df, {}, "ds-warm", "s", 1)
    snapshots.forget()
    loaded = snapshots.load("ds-warm", "s", 1)
    assert loaded.index._engine.is_mapping_populated
