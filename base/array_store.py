"""Storage for large arrays: in RAM, or as a file on disk (numpy memmap).

A memmap is an array whose data lives in a file. Numpy uses it like a normal
array, the operating system keeps the parts in use in RAM and writes the rest
back to the file when RAM gets tight. So a project can be larger than the RAM.

Rule: an array may take at most 1/32 of the RAM budget in RAM, larger arrays
go into a file. About 15 arrays are large (building parameters, lad, bad,
tree_id), each held about twice (model plus undo snapshot or loaded base
layer), so if each stays below 1/32 of the RAM everything together still fits.
The budget is 8 GB by default and set with the command line option --ram.

The files live in PALMPaint's tmp/ folder (not in git), one subfolder per
session. Each session keeps a lock on the file "lock" in its subfolder. The
operating system releases that lock when the program ends, also after a crash
or a kill. At startup, every subfolder whose lock can be taken belongs to a
program that is gone and is deleted. Subfolders of a PALMPaint window that is
still running stay locked and are left alone.

Before a file is created, the free disk space is checked and the file is
written once with normal file writes. A full disk then raises
NotEnoughDiskSpace, instead of killing the program when a memory-mapped page
cannot be written (SIGBUS on Linux, access violation on Windows).
"""

import atexit
import errno
import os
import shutil
import tempfile
import uuid
import weakref
from pathlib import Path

import numpy as np

if os.name == "nt":
    import msvcrt
else:
    import fcntl

DEFAULT_RAM_GB = 8.0
RAM_SHARE_PER_ARRAY = 32
_WRITE_CHUNK_BYTES = 64 * 1024 * 1024
_SESSION_PREFIX = "session_"

_ram_budget_bytes = int(DEFAULT_RAM_GB * 1024**3)
_tmp_root = None          # None: PALMPaint/tmp, fallback system temp folder
_session = None           # (session folder, open lock file)


class NotEnoughDiskSpace(OSError):
    """A large array does not fit into the free space of the tmp folder."""

    def __init__(self, needed, free, folder):
        self.needed = needed
        self.free = free
        self.folder = folder
        super().__init__(
            f"Not enough disk space in {folder} for a large array: "
            f"needs {needed / 1024**3:.1f} GB, {free / 1024**3:.1f} GB free. "
            "Free some space there, or start PALMPaint with a larger --ram "
            "so more arrays stay in RAM."
        )


def set_ram_budget(gb):
    """Set the RAM budget in GB (command line option --ram)."""
    global _ram_budget_bytes
    if gb <= 0:
        raise ValueError("The RAM budget must be positive")
    _ram_budget_bytes = int(gb * 1024**3)


def disk_threshold_bytes():
    """Arrays of this size or larger go into a file."""
    return _ram_budget_bytes // RAM_SHARE_PER_ARRAY


def set_tmp_root(path):
    """Use another folder for the session folders (tests). None: the default."""
    global _tmp_root
    _close_session()
    _tmp_root = None if path is None else Path(path)


def tmp_root():
    """The folder that holds the session folders, created if needed.

    PALMPaint/tmp next to the code. If that cannot be created (for example a
    read-only installation), a palmpaint folder in the system temp folder.
    """
    if _tmp_root is not None:
        _tmp_root.mkdir(parents=True, exist_ok=True)
        return _tmp_root
    default = Path(__file__).resolve().parent.parent / "tmp"
    try:
        default.mkdir(exist_ok=True)
        return default
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "palmpaint"
        fallback.mkdir(exist_ok=True)
        return fallback


def _try_lock(lock_file):
    """Lock an open file without waiting. True if this process now holds the lock."""
    try:
        if os.name == "nt":
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(lock_file):
    if os.name == "nt":
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def cleanup_stale_sessions(root=None):
    """Delete the session folders of programs that are no longer running.

    Returns the number of deleted folders. A folder whose lock is held by a
    running PALMPaint is left alone.
    """
    root = tmp_root() if root is None else Path(root)
    own = None if _session is None else _session[0]
    removed = 0
    for folder in root.glob(_SESSION_PREFIX + "*"):
        if not folder.is_dir() or folder == own:
            continue
        lock_path = folder / "lock"
        if lock_path.exists():
            try:
                lock_file = open(lock_path, "a+b")
            except OSError:
                continue
            try:
                if not _try_lock(lock_file):
                    continue          # the owner is still running
                _unlock(lock_file)
            finally:
                lock_file.close()
        shutil.rmtree(folder, ignore_errors=True)
        if not folder.exists():
            removed += 1
    return removed


def session_dir():
    """This session's folder, created and locked on first use."""
    global _session
    if _session is None:
        root = tmp_root()
        cleanup_stale_sessions(root)
        folder = root / f"{_SESSION_PREFIX}{os.getpid()}_{uuid.uuid4().hex[:8]}"
        folder.mkdir()
        lock_file = open(folder / "lock", "a+b")
        _try_lock(lock_file)
        _session = (folder, lock_file)
    return _session[0]


def _close_session():
    """Release the lock and delete this session's folder (normal exit, tests)."""
    global _session
    if _session is None:
        return
    folder, lock_file = _session
    _session = None
    try:
        _unlock(lock_file)
    except OSError:
        pass
    lock_file.close()
    # Files still mapped cannot be deleted on Windows, the next start cleans up
    shutil.rmtree(folder, ignore_errors=True)


atexit.register(_close_session)


def _remove_file(path):
    try:
        os.remove(path)
    except OSError:
        pass                      # still mapped on Windows, the next start cleans up


def _write_filled_file(path, nbytes, dtype, fill_value):
    """Write nbytes of fill_value with normal file writes, in chunks."""
    chunk_items = max(1, _WRITE_CHUNK_BYTES // dtype.itemsize)
    chunk = np.full(chunk_items, fill_value, dtype=dtype).tobytes()
    with open(path, "wb") as f:
        remaining = nbytes
        while remaining > 0:
            part = chunk if remaining >= len(chunk) else chunk[:remaining]
            f.write(part)
            remaining -= len(part)


def allocate(shape, dtype, *, fill_value=0, prefer_disk=None, name_prefix="array"):
    """Return an array filled with fill_value, in RAM or as a file in the session folder.

    prefer_disk forces one or the other, None decides by disk_threshold_bytes().
    The file is deleted as soon as the array is no longer used.
    """
    dtype = np.dtype(dtype)
    shape = tuple(int(dim) for dim in shape)
    nbytes = int(np.prod(shape, dtype=np.int64)) * dtype.itemsize
    on_disk = nbytes >= disk_threshold_bytes() if prefer_disk is None else bool(prefer_disk)
    if not on_disk or nbytes == 0:
        if fill_value == 0:
            return np.zeros(shape, dtype=dtype)
        return np.full(shape, fill_value, dtype=dtype)

    folder = session_dir()
    free = shutil.disk_usage(folder).free
    if free < nbytes:
        raise NotEnoughDiskSpace(nbytes, free, folder)
    path = folder / f"{name_prefix}_{uuid.uuid4().hex[:12]}.dat"
    try:
        _write_filled_file(path, nbytes, dtype, fill_value)
    except OSError as err:
        _remove_file(path)
        if err.errno == errno.ENOSPC:
            raise NotEnoughDiskSpace(nbytes, shutil.disk_usage(folder).free, folder) from err
        raise
    arr = np.memmap(path, dtype=dtype, mode="r+", shape=shape)
    weakref.finalize(arr, _remove_file, str(path))
    return arr
