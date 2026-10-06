"""Tests for the undo snapshot size used by the undo memory limit."""

import numpy as np

from base.gridmodel import GridModel


def test_state_nbytes():
    state = {
        "array": np.zeros((10), dtype=np.float32),              # 10 x 4 bytes = 40 bytes
        "dict": {"subarray": np.zeros((5, 5), dtype=np.int8)},  # 25 x 1 byte = 25 bytes
        "list": [np.zeros(1, dtype=np.int16)],                  # 1 x 2 bytes = 2 bytes
        "n": 42,                                                # not an array, 0 bytes
    }
    assert GridModel.state_nbytes(state) == 67                  # 40 + 25 + 2 + 0 = 67 bytes

def test_bigger_arrays():
    small = GridModel(10, 10, 1.0, 1.0).export_state()
    big = GridModel(100, 100, 1.0, 1.0).export_state()
    assert GridModel.state_nbytes(big) > GridModel.state_nbytes(small)