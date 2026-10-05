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
    # Bridges exist only in the file's buildings_3d, their decks hang above the ground
    snap['bridge_levels'] = model.bridge_levels()
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

# Side walls: name, row and column offset of the neighbour (row 0 = south), face_id
_WALL_SIDES = (("south", -1, 0, 1), ("north", 1, 0, 2), ("west", 0, -1, 3), ("east", 0, 1, 4))


def _building_wall_spans(snap: dict):
    """Visible part of every building cell's four side walls (culling).

    A side wall is visible from the neighbour's roof up to the cell's own roof:
    the neighbouring building, standing on solid ground, covers everything below
    its roof. Next to a cell without a building the wall reaches down to the
    cell's own ground, next to a building at least as tall it is hidden and left
    out. This also draws the step between two buildings of different height.

    Returns rows, cols, z0 (ground) and z1 (roof) of the building cells and
    {side: (visible, bottom)}, both arrays over those cells.
    """
    bh = snap['building_height']
    zt = snap['zt'].astype(np.float32)
    bldg = (bh != snap['FLOAT_FILL']) & (bh > 0)
    rows, cols = np.nonzero(bldg)
    z0 = zt[rows, cols]
    z1 = (z0 + bh[rows, cols]).astype(np.float32)

    roof = np.where(bldg, zt + np.where(bldg, bh, 0.0), -np.inf).astype(np.float32)
    roof_pad = np.pad(roof, 1, constant_values=-np.inf)   # no building outside the domain
    walls = {}
    for side, dr, dc, _face_id in _WALL_SIDES:
        bottom = np.maximum(z0, roof_pad[rows + 1 + dr, cols + 1 + dc])
        walls[side] = (bottom < z1 - 1e-3, bottom)
    return rows, cols, z0, z1, walls


def _build_building_mesh(snap: dict) -> 'pv.PolyData | None':
    """Visible building faces as a quad mesh coloured by building type.

    Roofs, and the side walls from _building_wall_spans(). Every face points
    outwards (corners anticlockwise seen from outside) for back-face culling.
    Each face cell stores [row, col, face_id] in cell_data['face_tag'] for
    future cell-picking (green walls, albedo editing).
    """
    res = snap['res']
    btype = snap['building_type']

    brows, bcols, z0, z1, walls = _building_wall_spans(snap)
    N = len(brows)
    if N == 0:
        return None

    x0 = (bcols * res).astype(np.float32)
    x1 = ((bcols + 1) * res).astype(np.float32)
    y0 = (brows * res).astype(np.float32)               # south edge of cell (row 0 = south)
    y1 = ((brows + 1) * res).astype(np.float32)         # north edge of cell

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
    _add_face_set(np.ones(N, dtype=bool), top_quads, 0)

    # Each wall from its visible bottom (neighbour's roof or own ground) to the roof
    zb = {side: bottom for side, (_visible, bottom) in walls.items()}
    side_quads = {
        "south": _stack(_col3(x0, y0, zb["south"]), _col3(x1, y0, zb["south"]),
                        _col3(x1, y0, z1), _col3(x0, y0, z1)),
        "north": _stack(_col3(x1, y1, zb["north"]), _col3(x0, y1, zb["north"]),
                        _col3(x0, y1, z1), _col3(x1, y1, z1)),
        "west":  _stack(_col3(x0, y1, zb["west"]), _col3(x0, y0, zb["west"]),
                        _col3(x0, y0, z1), _col3(x0, y1, z1)),
        "east":  _stack(_col3(x1, y0, zb["east"]), _col3(x1, y1, zb["east"]),
                        _col3(x1, y1, z1), _col3(x1, y0, z1)),
    }
    for side, _dr, _dc, face_id in _WALL_SIDES:
        _add_face_set(walls[side][0], side_quads[side], face_id)

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

def _build_bridge_mesh(snap: dict) -> 'pv.PolyData | None':
    """Bridge levels as boxes between their bottom and top, above the terrain.

    Every continuous run of voxels in a column is one box, so a column with a
    deck and a walkway above it keeps the open air in between. Levels lower
    than dz/2 (top == bottom) are flat for PALM and not drawn. Top and
    underside are always drawn, the underside keeps the free space below a
    bridge visible. A side face is skipped where the neighbouring column has
    the same level, so a deck only shows its outer edges.
    """
    rows, cols, bottom, top = snap['bridge_levels']
    keep = top > bottom
    if not keep.any():
        return None
    rows, cols, bottom, top = rows[keep], cols[keep], bottom[keep], top[keep]

    res = snap['res']
    zt = snap['zt'].astype(np.float32)
    x0 = (cols * res).astype(np.float32)
    x1 = ((cols + 1) * res).astype(np.float32)
    y0 = (rows * res).astype(np.float32)        # row 0 = south
    y1 = ((rows + 1) * res).astype(np.float32)
    z0 = zt[rows, cols] + bottom
    z1 = zt[rows, cols] + top

    # One integer key per level (column, bottom, top in dm) to find the same
    # level in the neighbouring column
    nx = int(snap['nx'])
    def level_key(r, c):
        return ((r.astype(np.int64) * nx + c) * 100000 + np.round(bottom * 10).astype(np.int64)) * 100000 \
            + np.round(top * 10).astype(np.int64)
    keys = level_key(rows, cols)
    def exposed(dr, dc):
        return ~np.isin(level_key(rows + dr, cols + dc), keys)

    everywhere = np.ones(len(rows), dtype=bool)
    faces_by_side = (
        (everywhere, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),      # top
        (everywhere, (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)),      # bottom
        (exposed(-1, 0), (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),  # south
        (exposed(1, 0), (x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)),   # north
        (exposed(0, -1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)),  # west
        (exposed(0, 1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)),   # east
    )

    lut = {tid: _color_to_uint8(cfg['display']['color']) for tid, cfg in BUILDING_CONFIG['types'].items()}
    cell_colors = np.full((len(rows), 3), [150, 150, 150], dtype=np.uint8)
    btype = snap['building_type'][rows, cols]
    for tid, color in lut.items():
        cell_colors[btype == tid] = color

    points, faces, colors = [], [], []
    offset = 0
    for mask, *corners in faces_by_side:
        n = int(mask.sum())
        if n == 0:
            continue
        quad = np.stack([np.column_stack([cx[mask], cy[mask], cz[mask]]) for cx, cy, cz in corners], axis=1)
        points.append(quad.reshape(n * 4, 3))
        first = np.arange(n, dtype=np.int32) * 4 + offset
        faces.append(np.column_stack([np.full(n, 4, dtype=np.int32), first, first + 1, first + 2, first + 3]))
        colors.append(cell_colors[mask])
        offset += n * 4

    mesh = pv.PolyData(np.vstack(points).astype(np.float32), np.vstack(faces).ravel())
    mesh.cell_data['RGB'] = np.vstack(colors)
    return mesh


def _build_lad_mesh(snap: dict) -> 'pv.PolyData | None':
    """Voxel mesh for resolved vegetation (LAD > 0), opaque, outside faces only.

    Canopy level k >= 1 spans zlad[k] - dz/2 to zlad[k] + dz/2 above the local
    terrain, so level 1 starts at the ground. PALM never reads level 0 (the
    surface itself, zlad = 0), so it is not drawn. A face is skipped where the
    neighbouring voxel has LAD too and covers it completely: above and below
    always, to the side only if both columns stand on the same terrain height.
    Each face gets the colour of its voxel's LAD value, see _lad_colors().
    """
    if 'lad' not in snap:
        return None
    lad  = snap['lad']   # (nzlad, ny, nx)
    zlad = np.asarray(snap['zlad'], dtype=np.float32)
    if lad.shape[0] < 2:
        return None
    filled = lad > 0
    filled[0] = False
    if not filled.any():
        return None

    res = float(snap['res'])
    zt  = snap['zt'].astype(np.float32)
    dz_lad = float(zlad[2] - zlad[1]) if len(zlad) > 2 else float(2 * zlad[1])

    # A side neighbour covers a face only if it stands on the same terrain height
    same_zt_x = np.abs(zt[:, 1:] - zt[:, :-1]) < 1e-3   # col and col + 1
    same_zt_y = np.abs(zt[1:, :] - zt[:-1, :]) < 1e-3   # row and row + 1

    s, lo, hi = slice(None), slice(None, -1), slice(1, None)
    faces_by_side = (
        # covered voxels, covering neighbours, terrain check, corners as (x, y, z) with 0 = low, 1 = high
        ((lo, s, s), (hi, s, s), None,      ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),  # top
        ((hi, s, s), (lo, s, s), None,      ((0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0))),  # bottom
        ((s, hi, s), (s, lo, s), same_zt_y, ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),  # south
        ((s, lo, s), (s, hi, s), same_zt_y, ((1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1))),  # north
        ((s, s, hi), (s, s, lo), same_zt_x, ((0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1))),  # west
        ((s, s, lo), (s, s, hi), same_zt_x, ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),  # east
    )

    points, faces, colors = [], [], []
    offset = 0
    hidden = np.empty_like(filled)
    for covered, covering, same_zt, corners in faces_by_side:
        hidden[:] = False
        hidden[covered] = filled[covering] if same_zt is None else filled[covering] & same_zt
        kz, rows, cols = np.nonzero(filled & ~hidden)
        n = len(kz)
        if n == 0:
            continue
        x = (np.stack([cols, cols + 1]) * res).astype(np.float32)   # row 0 = south
        y = (np.stack([rows, rows + 1]) * res).astype(np.float32)
        z_mid = zt[rows, cols] + zlad[kz]
        z = np.stack([z_mid - 0.5 * dz_lad, z_mid + 0.5 * dz_lad]).astype(np.float32)
        quad = np.stack([np.column_stack([x[i], y[j], z[k]]) for i, j, k in corners], axis=1)
        points.append(quad.reshape(n * 4, 3))
        first = np.arange(n, dtype=np.int32) * 4 + offset
        faces.append(np.column_stack([np.full(n, 4, dtype=np.int32), first, first + 1, first + 2, first + 3]))
        colors.append(_lad_colors(lad[kz, rows, cols].astype(np.float32)))
        offset += n * 4

    mesh = pv.PolyData(np.vstack(points), np.vstack(faces).ravel())
    mesh.cell_data['RGB'] = np.vstack(colors)
    return mesh


# LAD colours: piecewise linear between the stops. In the example drivers (palm_csd,
# palmgeo, palmpy, PALM test cases) the median voxel is 0.15 to 0.4 m2/m3 and a
# crown's densest voxel about 0.5, above 1.5 is rare. Above 1.5 a deeper green.
_LAD_COLOR_STOPS = np.array([0.0, 0.5, 1.5], dtype=np.float32)
_LAD_COLOR_RAMP  = np.array([[0x80, 0xa7, 0x53],    # 0, light green
                             [0x4e, 0x8a, 0x33],    # 0.5, middle green
                             [0x1c, 0x5c, 0x22]],   # 1.5, dark green
                            dtype=np.float32)
_LAD_COLOR_ABOVE = np.array([0x10, 0x3d, 0x13], dtype=np.uint8)


def _lad_colors(values: np.ndarray) -> np.ndarray:
    """uint8 RGB per voxel, interpolated between _LAD_COLOR_STOPS."""
    colors = np.column_stack([np.interp(values, _LAD_COLOR_STOPS, _LAD_COLOR_RAMP[:, ch])
                              for ch in range(3)]).round().astype(np.uint8)
    colors[values > _LAD_COLOR_STOPS[-1]] = _LAD_COLOR_ABOVE
    return colors


# ---------------------------------------------------------------------------
# Plotter
# ---------------------------------------------------------------------------

def _run_plotter(snap: dict) -> None:
    """Build the 3D scene and show the PyVista window (blocking)."""
    ground   = _build_ground_mesh(snap)
    bld_mesh = _build_building_mesh(snap)
    bridge_mesh = _build_bridge_mesh(snap)
    lad_mesh = _build_lad_mesh(snap)

    p = pv.Plotter(title='PALMPaint \u2014 3D View')
    p.background_color = '#87CEEB'

    # Back-face culling: the GPU skips faces turned away from the camera. All
    # meshes put their corners anticlockwise seen from outside, so normals point out.
    p.add_mesh(ground,   scalars='RGB', rgb=True, show_scalar_bar=False, culling='back')

    if bld_mesh is not None:
        p.add_mesh(bld_mesh, scalars='RGB', rgb=True, show_scalar_bar=False, culling='back')

    if bridge_mesh is not None:
        p.add_mesh(bridge_mesh, scalars='RGB', rgb=True, show_scalar_bar=False, culling='back')

    if lad_mesh is not None:
        # Opaque, because transparency is the most expensive part of rendering
        p.add_mesh(lad_mesh, scalars='RGB', rgb=True, show_scalar_bar=False, culling='back')

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
