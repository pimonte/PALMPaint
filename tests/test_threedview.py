"""Tests for the 3D view meshes: visible walls (culling) and outward faces.

The orientation test needs pyvista and is skipped without it, run it in an
environment that has pyvista (conda-forge).
"""

import numpy as np
import pytest

from base import threedview

FILL = -9999.0


def snap_for(building_height, zt=None, res=2.0):
    building_height = np.asarray(building_height, dtype=np.float32)
    ny, nx = building_height.shape
    return {
        "nx": nx, "ny": ny, "res": res, "dz": 1.0, "INT_FILL": -127, "FLOAT_FILL": FILL,
        "zt": np.zeros((ny, nx), np.float32) if zt is None else np.asarray(zt, np.float32),
        "building_height": building_height,
        "building_type": np.where(building_height > 0, 2, -127).astype(np.int8),
        "vegetation_type": np.full((ny, nx), -127, np.int8),
        "pavement_type": np.full((ny, nx), -127, np.int8),
        "water_type": np.full((ny, nx), -127, np.int8),
        "bridge_levels": (np.array([], int), np.array([], int), np.array([]), np.array([])),
    }


def wall(snap, col, side):
    """(visible, bottom) of one side wall of the building in row 0, column col."""
    rows, cols, _z0, _z1, walls = threedview._building_wall_spans(snap)
    i = int(np.nonzero((rows == 0) & (cols == col))[0][0])
    visible, bottom = walls[side]
    return bool(visible[i]), float(bottom[i])


def test_step_between_buildings_is_drawn_once():
    # 12 m building, 6 m building, empty cell
    snap = snap_for([[12.0, 6.0, FILL]])

    assert wall(snap, 0, "east") == (True, 6.0)    # the step, from B's roof up
    assert wall(snap, 1, "west")[0] is False       # hidden by the taller neighbour
    assert wall(snap, 1, "east") == (True, 0.0)    # next to empty ground: full wall
    assert wall(snap, 0, "west") == (True, 0.0)    # domain edge: full wall


def test_equal_neighbours_hide_their_walls_and_terrain_counts():
    snap = snap_for([[6.0, 6.0, 6.0]], zt=[[0.0, 0.0, 2.0]])

    assert wall(snap, 0, "east")[0] is False       # same roof height
    # the third building stands 2 m higher, its roof is at 8 m
    assert wall(snap, 2, "west") == (True, 6.0)
    assert wall(snap, 1, "east")[0] is False


def face_normals_and_centres(mesh):
    """Normal from the corner order (as the GPU sees it) and centre of every face."""
    quads = mesh.points[mesh.faces.reshape(-1, 5)[:, 1:]]
    normals = np.cross(quads[:, 1] - quads[:, 0], quads[:, 3] - quads[:, 0])
    return normals, quads.mean(axis=1)


def test_every_face_points_outwards():
    pytest.importorskip("pyvista")

    # one building cell (1, 1): x and y 2 to 4 m, z 0 to 6 m
    building = snap_for([[FILL] * 3, [FILL, 6.0, FILL], [FILL] * 3])
    # one LAD voxel on level 2 of column (0, 0): z 1 to 2 m
    lad = np.zeros((3, 3, 3), np.float32)
    lad[2, 0, 0] = 0.5
    building.update(lad=lad, zlad=np.array([0.0, 0.5, 1.5], np.float32))
    # one bridge deck in column (2, 2) from 3 to 4 m
    building["bridge_levels"] = (np.array([2]), np.array([2]), np.array([3.0]), np.array([4.0]))

    boxes = {
        "building": (threedview._build_building_mesh(building), np.array([3.0, 3.0, 3.0])),
        "lad": (threedview._build_lad_mesh(building), np.array([1.0, 1.0, 1.5])),
        "bridge": (threedview._build_bridge_mesh(building), np.array([5.0, 5.0, 3.5])),
    }
    for name, (mesh, centre) in boxes.items():
        normals, face_centres = face_normals_and_centres(mesh)
        outward = np.einsum("ij,ij->i", normals, face_centres - centre)
        assert np.all(outward > 0), f"{name}: a face points inwards"

    normals, _ = face_normals_and_centres(threedview._build_ground_mesh(building))
    assert np.all(normals[:, 2] > 0), "ground: a face points down"
