"""Tests for base/array_store.py: large arrays in files, leftovers, full disk."""

import gc
from collections import namedtuple

import numpy as np
import pytest

from base import array_store


@pytest.fixture
def store(tmp_path):
    """A RAM budget of 32 MB, so arrays from 1 MB go into files in tmp_path."""
    array_store.set_tmp_root(tmp_path)
    array_store.set_ram_budget(32 / 1024)
    yield tmp_path
    array_store.set_tmp_root(None)
    array_store.set_ram_budget(array_store.DEFAULT_RAM_GB)


def data_files(root):
    return sorted(root.glob("session_*/*.dat"))


def test_large_arrays_go_into_files_that_vanish_after_use(store):
    small = array_store.allocate((100, 100), np.float32)            # 40 kB
    large = array_store.allocate((4, 512, 512), np.float32, fill_value=-9999.0)   # 4 MB

    assert not isinstance(small, np.memmap)
    assert isinstance(large, np.memmap)
    assert np.all(large == -9999.0)
    assert len(data_files(store)) == 1

    del large
    gc.collect()
    assert data_files(store) == []


def test_only_folders_of_ended_sessions_are_removed(store):
    ended = store / "session_ended"
    ended.mkdir()
    (ended / "lock").touch()
    (ended / "lad_1.dat").write_bytes(b"x" * 1000)

    running = store / "session_running"
    running.mkdir()
    lock_file = open(running / "lock", "a+b")
    assert array_store._try_lock(lock_file)    # as a running PALMPaint holds it

    try:
        assert array_store.cleanup_stale_sessions() == 1
        assert not ended.exists()
        assert running.exists()
    finally:
        lock_file.close()


def test_full_disk_gives_an_error_instead_of_a_crash(store, monkeypatch):
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(array_store.shutil, "disk_usage", lambda path: Usage(10, 10, 0))

    with pytest.raises(array_store.NotEnoughDiskSpace):
        array_store.allocate((4, 512, 512), np.float32)
    assert data_files(store) == []
