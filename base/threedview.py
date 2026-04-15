"""
3D view of the PALMPaint grid using PyVista.

Opens a standalone VTK window in a daemon thread (view-only).
Architecture supports future face-picking for green wall / albedo editing.

Coordinate convention (PALM → PyVista):
    x = col × res   (west → east)
    y = row × res   (south → north, row 0 = south boundary)
    z = height (m)

Face IDs stored in mesh.cell_data['face_tag'][:, 2]:
    0 = top,  1 = south,  2 = north,  3 = west,  4 = east
"""

import threading

import numpy as np

try:
    import pyvista as pv
    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False

from base.surface_config import SURFACE_CONFIG
from base.building_config import BUILDING_CONFIG


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _color_to_uint8(color_str: str) -> np.ndarray:
    """Parse CSS hex or named color to uint8 [r, g, b] array."""
    s = color_str.strip()
    if s.startswith('#'):
        h = s[1:]
        if len(h) == 3:
            h = h[0] * 2 + h[1] * 2 + h[2] * 2
        return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], dtype=np.uint8)
    # Named color via PyVista (wraps VTK colour table)
    c = pv.Color(s)
    return (np.array(c.float_rgb) * 255).astype(np.uint8)


def _surface_color_lut(section: str) -> dict:
    """Return {type_id: uint8 [r,g,b]} for a SURFACE_CONFIG section."""
    return {
        tid: _color_to_uint8(cfg['display']['color'])
        for tid, cfg in SURFACE_CONFIG[section]['types'].items()
    }


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def _snapshot(model) -> dict:
    """Copy all arrays needed for rendering (thread-safe snapshot)."""
    snap = {
        'nx': model.nx,
        'ny': model.ny,
        'res': float(model.res),
        'dz': float(model.dz),
        'INT_FILL': int(model.INT_FILL),
        'FLOAT_FILL': float(model.FLOAT_FILL),
        'zt': model.zt.copy(),
        'vegetation_type': model.vegetation_type.copy(),
        'pavement_type': model.pavement_type.copy(),
        'water_type': model.water_type.copy(),
        'building_height': model.building_height.copy(),
        'building_type': model.building_type.copy(),
        'building_id': model.building_id.copy(),
    }
    rv = model.resolved_vegetation
    if rv and 'lad' in rv and rv['lad'] is not None:
        snap['zlad'] = rv['zlad'].copy()
        snap['lad'] = rv['lad'].copy()
    return snap


# ---------------------------------------------------------------------------
# Ground surface mesh
# ---------------------------------------------------------------------------

def _build_ground_mesh(snap: dict) -> 'pv.PolyData':
    """Terrain surface as a quad mesh coloured by surface type."""
    ny, nx = snap['ny'], snap['nx']
    res = snap['res']
    INT_FILL = snap['INT_FILL']
    FLOAT_FILL = snap['FLOAT_FILL']
    zt = snap['zt'].astype(np.float32)

    # --- Vertex positions ---
    # Vertex (jv, iv): x = iv*res, y = (ny-jv)*res, z = bilinear avg of neighbours
    zt_pad = np.pad(zt, ((1, 1), (1, 1)), mode='edge')  # (ny+2, nx+2)
    vertex_z = 0.25 * (
        zt_pad[0:ny + 1, 0:nx + 1] +
        zt_pad[0:ny + 1, 1:nx + 2] +
        zt_pad[1:ny + 2, 0:nx + 1] +
        zt_pad[1:ny + 2, 1:nx + 2]
    )  # (ny+1, nx+1)

    jv, iv = np.meshgrid(np.arange(ny + 1), np.arange(nx + 1), indexing='ij')
    x_pts = (iv * res).ravel().astype(np.float32)
    y_pts = (jv * res).ravel().astype(np.float32)
    z_pts = vertex_z.ravel().astype(np.float32)
    pts = np.column_stack([x_pts, y_pts, z_pts])  # ((ny+1)*(nx+1), 3)

    # --- Quad faces: cell (r, c) → vertices at jv=r,r+1 and iv=c,c+1 ---
    r_arr, c_arr = np.meshgrid(np.arange(ny), np.arange(nx), indexing='ij')
    r_f = r_arr.ravel()
    c_f = c_arr.ravel()
    stride = nx + 1
    i_nw = r_f * stride + c_f
    i_ne = r_f * stride + (c_f + 1)
    i_se = (r_f + 1) * stride + (c_f + 1)
    i_sw = (r_f + 1) * stride + c_f
    n_cells = ny * nx
    faces = np.column_stack([
        np.full(n_cells, 4, dtype=np.int32),
        i_nw, i_ne, i_se, i_sw,
    ]).ravel()

    # --- Per-cell colours ---
    veg_lut = _surface_color_lut('vegetation')
    pave_lut = _surface_color_lut('pavement')
    water_lut = _surface_color_lut('water')

    cell_colors = np.full((ny, nx, 3), 160, dtype=np.uint8)  # default gray

    veg = snap['vegetation_type']
    pave = snap['pavement_type']
    water = snap['water_type']
    bh = snap['building_height']

    for tid, col in veg_lut.items():
        cell_colors[veg == tid] = col
    for tid, col in pave_lut.items():
        cell_colors[pave == tid] = col
    for tid, col in water_lut.items():
        cell_colors[water == tid] = col

    bldg_mask = (bh != FLOAT_FILL) & (bh > 0)
    cell_colors[bldg_mask] = np.array([180, 160, 140], dtype=np.uint8)

    mesh = pv.PolyData(pts, faces)
    mesh.cell_data['RGB'] = cell_colors.reshape(n_cells, 3)
    return mesh


# ---------------------------------------------------------------------------
# Building mesh
# ---------------------------------------------------------------------------

def _build_building_mesh(snap: dict) -> 'pv.PolyData | None':
    """Exterior building faces as a quad mesh coloured by building type.

    Each face cell stores [row, col, face_id] in cell_data['face_tag'] for
    future cell-picking (green walls, albedo editing).
    """
    res = snap['res']
    FLOAT_FILL = snap['FLOAT_FILL']
    bh = snap['building_height']
    zt = snap['zt'].astype(np.float32)
    btype = snap['building_type']

    bldg_mask = (bh != FLOAT_FILL) & (bh > 0)
    if not bldg_mask.any():
        return None

    brows, bcols = np.where(bldg_mask)
    N = len(brows)

    x0 = (bcols * res).astype(np.float32)
    x1 = ((bcols + 1) * res).astype(np.float32)
    y0 = (brows * res).astype(np.float32)               # south edge of cell (row 0 = south)
    y1 = ((brows + 1) * res).astype(np.float32)         # north edge of cell
    z0 = zt[brows, bcols]
    z1 = (zt[brows, bcols] + bh[brows, bcols]).astype(np.float32)

    # Exterior face detection using padded mask
    pad = np.pad(bldg_mask, ((1, 1), (1, 1)), constant_values=False)
    # pad[r+1, c+1] == bldg_mask[r, c];  row 0 = south, row increases northward
    ext_south = ~pad[brows,     bcols + 1]  # neighbour at row-1 (south, lower row index)
    ext_north = ~pad[brows + 2, bcols + 1]  # neighbour at row+1 (north, higher row index)
    ext_west  = ~pad[brows + 1, bcols]      # neighbour at col-1
    ext_east  = ~pad[brows + 1, bcols + 2]  # neighbour at col+1

    # Building-type colour lookup
    btype_lut = {}
    for tid, cfg in BUILDING_CONFIG['types'].items():
        btype_lut[tid] = _color_to_uint8(cfg['display']['color'])
    default_bc = np.array([150, 150, 150], dtype=np.uint8)

    def _bcolors(mask: np.ndarray) -> np.ndarray:
        bt = btype[brows[mask], bcols[mask]]
        colors = np.full((mask.sum(), 3), default_bc, dtype=np.uint8)
        for tid, col in btype_lut.items():
            colors[bt == tid] = col
        return colors

    all_pts: list = []
    all_faces: list = []
    all_colors: list = []
    all_tags: list = []
    pt_off = 0

    def _add_face_set(mask: np.ndarray, quad_verts: np.ndarray, face_id: int) -> None:
        """Append a set of quad faces.

        quad_verts: (N_total, 4, 3) — one quad per building cell; mask selects which.
        """
        nonlocal pt_off
        n = int(mask.sum())
        if n == 0:
            return
        sel = quad_verts[mask]          # (n, 4, 3)
        all_pts.append(sel.reshape(n * 4, 3))
        base = np.arange(n, dtype=np.int32) * 4 + pt_off
        fv = np.column_stack([np.full(n, 4, dtype=np.int32), base, base+1, base+2, base+3])
        all_faces.append(fv)
        pt_off += n * 4
        all_colors.append(_bcolors(mask))
        tags = np.column_stack([brows[mask], bcols[mask], np.full(n, face_id, dtype=np.int32)])
        all_tags.append(tags)

    # Precompute corner stacks for all N cells (vectorized)
    def _stack(a, b, c, d) -> np.ndarray:
        """Stack 4 point columns → (N, 4, 3)."""
        return np.stack([a, b, c, d], axis=1)   # each is (N, 3)

    def _col3(a, b, c) -> np.ndarray:
        return np.column_stack([a, b, c]).astype(np.float32)

    top_quads = _stack(
        _col3(x0, y0, z1), _col3(x1, y0, z1),
        _col3(x1, y1, z1), _col3(x0, y1, z1),
    )
    south_quads = _stack(
        _col3(x0, y0, z0), _col3(x1, y0, z0),
        _col3(x1, y0, z1), _col3(x0, y0, z1),
    )
    north_quads = _stack(
        _col3(x1, y1, z0), _col3(x0, y1, z0),
        _col3(x0, y1, z1), _col3(x1, y1, z1),
    )
    west_quads = _stack(
        _col3(x0, y1, z0), _col3(x0, y0, z0),
        _col3(x0, y0, z1), _col3(x0, y1, z1),
    )
    east_quads = _stack(
        _col3(x1, y0, z0), _col3(x1, y1, z0),
        _col3(x1, y1, z1), _col3(x1, y0, z1),
    )

    _add_face_set(np.ones(N, dtype=bool), top_quads,   0)
    _add_face_set(ext_south,              south_quads,  1)
    _add_face_set(ext_north,              north_quads,  2)
    _add_face_set(ext_west,               west_quads,   3)
    _add_face_set(ext_east,               east_quads,   4)

    if not all_pts:
        return None

    points = np.vstack(all_pts).astype(np.float32)
    faces  = np.vstack(all_faces).ravel().astype(np.int32)
    colors = np.vstack(all_colors)
    tags   = np.vstack(all_tags).astype(np.int32)

    mesh = pv.PolyData(points, faces)
    mesh.cell_data['RGB']      = colors
    mesh.cell_data['face_tag'] = tags
    return mesh


# ---------------------------------------------------------------------------
# LAD / vegetation volume mesh
# ---------------------------------------------------------------------------

def _build_lad_mesh(snap: dict) -> 'pv.PolyData | None':
    """Voxel mesh for resolved vegetation (LAD > 0), terrain-offset, semi-transparent.

    Each voxel is placed at zt[row, col] + zlad[kz] so trees sit on top of terrain.
    """
    if 'lad' not in snap:
        return None
    lad  = snap['lad']   # (nzlad, ny, nx)
    zlad = snap['zlad']  # (nzlad,)
    res = float(snap['res'])
    zt  = snap['zt'].astype(np.float32)
    nz  = lad.shape[0]

    if nz == 0 or not np.any(lad > 0):
        return None

    dz_lad = float(zlad[1] - zlad[0]) if nz > 1 else float(snap['dz'])

    kz_arr, rows, cols = np.where(lad > 0)
    N = len(kz_arr)

    x0 = (cols * res).astype(np.float32)
    x1 = ((cols + 1) * res).astype(np.float32)
    y0 = (rows * res).astype(np.float32)
    y1 = ((rows + 1) * res).astype(np.float32)
    zt_cell = zt[rows, cols]
    z_bot = (zt_cell + zlad[kz_arr]).astype(np.float32)
    z_top = (z_bot + dz_lad).astype(np.float32)

    def _col3(a, b, c):
        return np.column_stack([a, b, c]).astype(np.float32)

    # 6 faces per voxel (all faces — LAD is sparse so interior waste is acceptable)
    face_defs = [
        (_col3(x0, y0, z_top), _col3(x1, y0, z_top), _col3(x1, y1, z_top), _col3(x0, y1, z_top)),  # top
        (_col3(x0, y1, z_bot), _col3(x1, y1, z_bot), _col3(x1, y0, z_bot), _col3(x0, y0, z_bot)),  # bottom
        (_col3(x0, y0, z_bot), _col3(x1, y0, z_bot), _col3(x1, y0, z_top), _col3(x0, y0, z_top)),  # south
        (_col3(x1, y1, z_bot), _col3(x0, y1, z_bot), _col3(x0, y1, z_top), _col3(x1, y1, z_top)),  # north
        (_col3(x0, y1, z_bot), _col3(x0, y0, z_bot), _col3(x0, y0, z_top), _col3(x0, y1, z_top)),  # west
        (_col3(x1, y0, z_bot), _col3(x1, y1, z_bot), _col3(x1, y1, z_top), _col3(x1, y0, z_top)),  # east
    ]

    all_pts:   list = []
    all_faces: list = []
    pt_off = 0

    for p0, p1, p2, p3 in face_defs:
        pts = np.stack([p0, p1, p2, p3], axis=1).reshape(N * 4, 3)  # (N*4, 3)
        all_pts.append(pts)
        base = np.arange(N, dtype=np.int32) * 4 + pt_off
        fv = np.column_stack([np.full(N, 4, dtype=np.int32), base, base+1, base+2, base+3])
        all_faces.append(fv)
        pt_off += N * 4

    points = np.vstack(all_pts).astype(np.float32)
    faces  = np.vstack(all_faces).ravel().astype(np.int32)
    return pv.PolyData(points, faces)


# ---------------------------------------------------------------------------
# Plotter
# ---------------------------------------------------------------------------

def _run_plotter(snap: dict) -> None:
    """Build the 3D scene and show the PyVista window (blocking)."""
    ground   = _build_ground_mesh(snap)
    bld_mesh = _build_building_mesh(snap)
    lad_mesh = _build_lad_mesh(snap)

    p = pv.Plotter(title='PALMPaint \u2014 3D View')
    p.background_color = '#87CEEB'

    p.add_mesh(ground,   scalars='RGB', rgb=True, show_scalar_bar=False)

    if bld_mesh is not None:
        p.add_mesh(bld_mesh, scalars='RGB', rgb=True, show_scalar_bar=False)

    if lad_mesh is not None:
        p.add_mesh(lad_mesh, color='#2d6a0a', opacity=0.55, show_scalar_bar=False)

    p.show_axes()

    # Camera: look from south toward north so east is on the right,
    # matching the 2D canvas orientation (north up, east right).
    nx_m = float(snap['nx'] * snap['res'])
    ny_m = float(snap['ny'] * snap['res'])
    dist = (nx_m ** 2 + ny_m ** 2) ** 0.5
    p.camera.position    = (nx_m / 2.0, -ny_m * 0.5, dist * 0.8)
    p.camera.focal_point = (nx_m / 2.0,  ny_m / 2.0, 0.0)
    p.camera.up          = (0.0, 0.0, 1.0)

    p.show()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def open_3d_view(model) -> threading.Thread:
    """Snapshot the model and open the 3D view in a daemon thread.

    Returns the thread so the caller can track whether the window is still open.
    """
    snap = _snapshot(model)
    t = threading.Thread(target=_run_plotter, args=(snap,), daemon=True)
    t.start()
    return t
