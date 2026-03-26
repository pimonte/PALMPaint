"""
tree_generator_core.py

Generates idealised 3-D LAD fields for individual trees.

Two consistent modes:

(A) profile_mode="density" (default):
    - A vertical Beta profile f(zeta) is prescribed as a *density profile*.
    - At each height z, LAD is distributed uniformly over the crown cross-section A(z).
    - The mean over the crown area (excluding air) equals exactly LAD_1D(z).

(B) profile_mode="geometry":
    - A vertical Beta profile f(zeta) is prescribed as a *cross-section fraction profile*.
    - The crown cross-section A(z) is shaped so that A(z)/A_proj = f(zeta)/max(f).
    - LAD within the crown volume is constant = LAD0.
    - The mean over the crown area (excluding air) is constant (=LAD0).
    - The mean over the reference area A_proj (including air) reproduces the desired profile.

Reference area:
    A_proj = pi * (Dc/2)^2   (crown projection based on crown_diameter)
LAI:
    LAI is always defined over A_proj (crown projection).

Scaling:
    Exactly one of {lai, lad_max} must be provided.
    The other is computed and returned in the result dict.

Note:
    In geometry mode, lad_max == LAD0 (constant volumetric density).

Adapted for PALMPaint: scipy replaced by math.gamma-based beta PDF (no extra deps).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any

import numpy as np


ProfileMode = Literal["density", "geometry"]
LadModel = Literal["beta_density", "palm_extinction"]
# PALM crown shape IDs (consistent with vegetation.py):
#   1 = Ellipsoid, 2 = Cylinder, 3 = Cone, 4 = Inv. Cone, 5 = Paraboloid, 6 = Inv. Paraboloid


@dataclass(frozen=True)
class Grid:
    dx: float = 1.0
    dy: float = 1.0
    dz: float = 1.0
    pad_xy: float = 5.0
    pad_z: float = 2.0


@dataclass(frozen=True)
class TreeParams:
    # Geometry
    max_tree_height: float            # H [m], ground to crown tip (crown_top = H)
    crown_diameter: float             # Dc [m] -> also reference radius for A_proj
    trunk_diameter: float             # Dt [m]
    crown_shape: int                  # PALM crown shape 1-6 (beta_density mode only)
    crown_ratio: float                # crown_height / crown_diameter (PALM convention)

    # Vertical profile f(zeta): Beta(alpha, beta) over zeta in [0,1]
    alpha: float
    beta: float

    # Scaling: EXACTLY ONE must be set
    lai: Optional[float] = None       # LAI over crown projection [m²/m²]
    lad_max: Optional[float] = None   # max LAD [m²/m³] (density mode: peak; geometry mode: constant)

    # Modus
    profile_mode: ProfileMode = "density"

    lad_model: LadModel = "palm_extinction"
    palm_extinction_k: float = 0.6  # entspricht self.tree_sphere_extinction in PALM

    # BAD (Branch Area Density)
    bad_lad_ratio: float = 0.025  # BAD = LAD * ratio im Kronenvolumen; Stamm bekommt BAD=1.0


# ----------------------------
# Grid
# ----------------------------

def _make_grid(params: TreeParams, grid: Grid):
    H = params.max_tree_height  # Tree height
    Dc = params.crown_diameter  # Crown diameter

    # Total tree domain size
    Lx = Dc + 2.0 * grid.pad_xy  # Total x length
    Ly = Dc + 2.0 * grid.pad_xy  # Total y length
    Lz = H + grid.pad_z          # Total z length

    # Discretization sizes to integer number of cells.
    # nx and ny are forced to odd so there is always a cell centred exactly at
    # x=0 / y=0 (the trunk position).  This keeps the generator footprint
    # aligned with the hover-preview circle in the editor.
    nx = int(np.ceil(Lx / grid.dx))
    if nx % 2 == 0:
        nx += 1
    ny = int(np.ceil(Ly / grid.dy))
    if ny % 2 == 0:
        ny += 1
    nz = int(np.ceil(Lz / grid.dz))

    # Calculate grid coordinates to m (cell-centered).
    # Use the actual discretised extent (nx*dx) for centering so the domain is
    # always perfectly symmetric around (0, 0) regardless of resolution.
    x = (np.arange(nx) + 0.5) * grid.dx - 0.5 * nx * grid.dx
    y = (np.arange(ny) + 0.5) * grid.dy - 0.5 * ny * grid.dy
    z = (np.arange(nz) + 0.5) * grid.dz

    # create 3D meshgrid
    X, Y, Z = np.meshgrid(x, y, z, indexing="xy")
    # transpose to (z,y,x) ordering for PALM compatibility
    X = np.transpose(X, (2, 0, 1))
    Y = np.transpose(Y, (2, 0, 1))
    Z = np.transpose(Z, (2, 0, 1))

    return x, y, z, X, Y, Z


# ----------------------------
# Tree-Meta
# ----------------------------

def _base_meta(params: TreeParams) -> Dict[str, float]:
    H = params.max_tree_height
    Dc = params.crown_diameter

    # crown_ratio = crown_height / crown_diameter  (PALM-Konvention)
    crown_height = params.crown_ratio * Dc
    # Ensure crown height does not exceed tree height
    crown_height = min(crown_height, H)

    crown_top_z = H
    crown_base_z = H - crown_height  # Crown base height

    Rc = Dc / 2.0   # Crown radius
    Rt = params.trunk_diameter / 2.0  # Trunk radius

    # Projected crown area
    A_proj = float(np.pi * Rc**2)

    return dict(
        crown_base_z=float(crown_base_z),
        crown_top_z=float(crown_top_z),
        crown_height=float(crown_height),
        Rc=float(Rc),
        Rt=float(Rt),
        A_proj=float(A_proj),
    )


# ----------------------------
# Kronen-/Stamm-Masken
# ----------------------------

def _trunk_mask(params: TreeParams, X, Y, Z, meta: Dict[str, float]) -> np.ndarray:
    r = np.sqrt(X**2 + Y**2)
    Rt = meta["Rt"]
    crown_base_z = meta["crown_base_z"]
    return (r <= Rt) & (Z >= 0.0) & (Z <= crown_base_z)


def _crown_mask_shape_density(params: TreeParams, X, Y, Z, meta: Dict[str, float]) -> np.ndarray:
    """PALM-konforme Kronenformen (shape 1-6), nur im beta_density-Modus genutzt.

    zeta=0 bei crown_base, zeta=1 bei crown_top.
    """
    shape = int(params.crown_shape)
    crown_base_z = meta["crown_base_z"]
    crown_top_z  = meta["crown_top_z"]
    crown_height = meta["crown_height"]
    Rc = meta["Rc"]

    r = np.sqrt(X**2 + Y**2)
    zeta = (Z - crown_base_z) / max(crown_height, 1e-12)
    inside_z = (Z >= crown_base_z) & (Z <= crown_top_z)

    if shape == 1:  # Ellipsoid
        zc = 0.5 * (crown_base_z + crown_top_z)
        c  = crown_height / 2.0
        return inside_z & (((X / max(Rc, 1e-12)) ** 2
                            + (Y / max(Rc, 1e-12)) ** 2
                            + ((Z - zc) / max(c, 1e-12)) ** 2) <= 1.0)

    elif shape == 2:  # Zylinder
        return inside_z & (r <= Rc)

    elif shape == 3:  # Kegel – unten breit, oben spitz
        Rz = Rc * (1.0 - zeta)
        return inside_z & (r <= np.clip(Rz, 0.0, Rc))

    elif shape == 4:  # Inv. Kegel – unten spitz, oben breit
        Rz = Rc * zeta
        return inside_z & (r <= np.clip(Rz, 0.0, Rc))

    elif shape == 5:  # Paraboloid – unten breit, oben spitz
        Rz = Rc * np.sqrt(np.clip(1.0 - zeta, 0.0, 1.0))
        return inside_z & (r <= Rz)

    elif shape == 6:  # Inv. Paraboloid – unten spitz, oben breit
        Rz = Rc * np.sqrt(np.clip(zeta, 0.0, 1.0))
        return inside_z & (r <= Rz)

    else:
        raise ValueError(f"Unbekannte PALM-Kronenform: {shape} (erwartet 1-6)")


def _beta_pdf_numpy(x: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    """Beta PDF evaluated at x using only math.gamma (no scipy dependency).

    f(x; alpha, beta) = x^(alpha-1) * (1-x)^(beta-1) / B(alpha, beta)
    where B(alpha, beta) = Gamma(alpha)*Gamma(beta)/Gamma(alpha+beta)
    """
    B = math.gamma(alpha) * math.gamma(beta) / math.gamma(alpha + beta)
    return (x ** (alpha - 1.0)) * ((1.0 - x) ** (beta - 1.0)) / B


def _beta_pdf_zeta(zeta: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    zeta = np.clip(zeta, 1e-12, 1.0 - 1e-12)
    return _beta_pdf_numpy(zeta, alpha, beta)


def _beta_peak_value(alpha: float, beta: float) -> float:
    zz = np.linspace(1e-9, 1.0 - 1e-9, 10000)
    vals = _beta_pdf_numpy(zz, alpha, beta)
    return float(vals.max())


def _crown_mask_from_profile_geometry(params: TreeParams, X, Y, Z, meta: Dict[str, float]) -> np.ndarray:
    """
    Geometry-mode: Achsensymmetrische Krone, bei der der Querschnitt A(z) dem Profil folgt.

    area_fraction(z) = f(zeta) / f_peak  in [0,1]
    R(z) = R_proj * sqrt(area_fraction(z))
    """
    crown_base_z = meta["crown_base_z"]
    crown_top_z = meta["crown_top_z"]
    crown_height = meta["crown_height"]
    R_proj = meta["Rc"]

    zeta = (Z - crown_base_z) / max(crown_height, 1e-12)
    inside_z = (Z >= crown_base_z) & (Z <= crown_top_z)

    f = _beta_pdf_zeta(np.clip(zeta, 0.0, 1.0), params.alpha, params.beta)
    f_peak = _beta_peak_value(params.alpha, params.beta)

    area_fraction = np.clip(f / max(f_peak, 1e-12), 0.0, 1.0)
    Rz = R_proj * np.sqrt(area_fraction)

    r = np.sqrt(X**2 + Y**2)
    return inside_z & (r <= Rz)


# ----------------------------
# Skalierung LAI <-> LAD_max
# ----------------------------

def _compute_scaling(params: TreeParams, meta: Dict[str, float]) -> Dict[str, float]:
    lai_set = params.lai is not None
    ladmax_set = params.lad_max is not None
    if lai_set == ladmax_set:
        raise ValueError("Bitte genau eines angeben: entweder lai ODER lad_max (nicht beides, nicht keins).")

    h_c = meta["crown_height"]
    f_peak = _beta_peak_value(params.alpha, params.beta)

    if params.profile_mode == "density":
        # LAD_1D(z) = S * f(zeta),   LAI = S*h_c,   LAD_max = S*f_peak
        if lai_set:
            lai = float(params.lai)
            S = lai / h_c
            lad_max = S * f_peak
        else:
            lad_max = float(params.lad_max)
            S = lad_max / f_peak
            lai = S * h_c
        return {"scale": float(S), "lai": float(lai), "lad_max": float(lad_max), "f_peak": float(f_peak)}

    # geometry mode:
    # LAD(x,y,z) = LAD0 constant within the crown volume.
    # LAI = LAD0 * h_c  => LAD0 = LAI/h_c
    # lad_max == LAD0 (constant)
    if lai_set:
        lai = float(params.lai)
        LAD0 = lai / h_c
        lad_max = LAD0
    else:
        lad_max = float(params.lad_max)
        LAD0 = lad_max
        lai = LAD0 * h_c

    return {"scale": float(LAD0), "lai": float(lai), "lad_max": float(lad_max), "f_peak": float(f_peak)}


def _lad_field_palm_extinction(params: TreeParams, X, Y, Z, meta: Dict[str, float], lad_max: float) -> np.ndarray:
    """
    PALM extinction model for all crown shapes 1-6.

    For each point a normalised distance r_eff is computed:
      r_eff = 0  at the centre / on the symmetry axis
      r_eff = 1  at the crown surface
    Then:  LAD = lad_max * exp(-k * (1 - r_eff))   for points inside the crown

    Shape-specific R(z) formulae (as in PALM vegetation.py):
      1 Ellipsoid:        r_eff = sqrt((x/Rx)^2+(y/Rx)^2+((z-zc)/Rz)^2)
      2 Cylinder:         r_eff = max(sqrt((x/Rx)^2+(y/Rx)^2), |z-zc|/Rz)
      3 Cone:             R(z)  = Rx*(1-zeta),   r_eff = max(r_h(z), r_v)
      4 Inv. Cone:        R(z)  = Rx*zeta,        r_eff = max(r_h(z), r_v)
      5 Paraboloid:       R(z)  = Rx*sqrt(1-zeta),r_eff = max(r_h(z), r_v)
      6 Inv. Paraboloid:  R(z)  = Rx*sqrt(zeta),  r_eff = max(r_h(z), r_v)
    """
    shape = int(params.crown_shape)
    Rx = max(meta["Rc"], 1e-12)
    crown_base_z  = meta["crown_base_z"]
    crown_top_z   = meta["crown_top_z"]
    crown_height  = max(meta["crown_height"], 1e-12)
    Rz = crown_height / 2.0
    zc = 0.5 * (crown_base_z + crown_top_z)
    k  = float(params.palm_extinction_k)

    # Shared normalized distances
    r_v     = np.abs(Z - zc) / Rz                                        # 0=center, 1=top/bottom face
    inside_z = (Z >= crown_base_z) & (Z <= crown_top_z)
    zeta     = np.clip((Z - crown_base_z) / crown_height, 0.0, 1.0)     # 0=base, 1=top

    lad = np.zeros_like(X, dtype=float)

    if shape == 1:  # Ellipsoid
        r_eff  = np.sqrt((X / Rx)**2 + (Y / Rx)**2 + ((Z - zc) / Rz)**2)
        inside = r_eff <= 1.0
        lad[inside] = float(lad_max) * np.exp(-k * (1.0 - r_eff[inside]))

    elif shape == 2:  # Zylinder
        r_h   = np.sqrt((X / Rx)**2 + (Y / Rx)**2)
        r_eff = np.maximum(r_h, r_v)
        inside = inside_z & (r_h <= 1.0)
        lad[inside] = float(lad_max) * np.exp(-k * (1.0 - r_eff[inside]))

    elif shape == 3:  # Cone: wide at base, tapered at top
        R_cone = np.where(inside_z, Rx * (1.0 - zeta), 1e-12)
        r_h    = np.sqrt(X**2 + Y**2) / np.maximum(R_cone, 1e-12)
        r_eff  = np.maximum(r_h, r_v)
        inside = inside_z & (r_h <= 1.0)
        lad[inside] = float(lad_max) * np.exp(-k * (1.0 - r_eff[inside]))

    elif shape == 4:  # Inv. Cone: tapered at base, wide at top
        R_cone = np.where(inside_z, Rx * zeta, 1e-12)
        r_h    = np.sqrt(X**2 + Y**2) / np.maximum(R_cone, 1e-12)
        r_eff  = np.maximum(r_h, r_v)
        inside = inside_z & (r_h <= 1.0)
        lad[inside] = float(lad_max) * np.exp(-k * (1.0 - r_eff[inside]))

    elif shape == 5:  # Paraboloid: wide at base, tapered at top
        R_par  = np.where(inside_z, Rx * np.sqrt(np.clip(1.0 - zeta, 0.0, 1.0)), 1e-12)
        r_h    = np.sqrt(X**2 + Y**2) / np.maximum(R_par, 1e-12)
        r_eff  = np.maximum(r_h, r_v)
        inside = inside_z & (r_h <= 1.0)
        lad[inside] = float(lad_max) * np.exp(-k * (1.0 - r_eff[inside]))

    elif shape == 6:  # Inv. Paraboloid: tapered at base, wide at top
        R_par  = np.where(inside_z, Rx * np.sqrt(np.clip(zeta, 0.0, 1.0)), 1e-12)
        r_h    = np.sqrt(X**2 + Y**2) / np.maximum(R_par, 1e-12)
        r_eff  = np.maximum(r_h, r_v)
        inside = inside_z & (r_h <= 1.0)
        lad[inside] = float(lad_max) * np.exp(-k * (1.0 - r_eff[inside]))

    else:
        raise ValueError(f"Unknown PALM crown shape: {shape}")

    return lad


# ----------------------------
# Public API
# ----------------------------

def generate_tree(params: TreeParams, grid: Grid = Grid()) -> Dict[str, Any]:
    x, y, z, X, Y, Z = _make_grid(params, grid)
    meta = _base_meta(params)

    trunk = _trunk_mask(params, X, Y, Z, meta)

    # --- Scaling (LAI <-> LAD_max) ---
    lai_set = params.lai is not None
    ladmax_set = params.lad_max is not None
    if lai_set == ladmax_set:
        raise ValueError("Provide exactly one of: lai OR lad_max (not both, not neither).")

    # Reference area for LAI:
    A_proj = meta["A_proj"]
    dV = grid.dx * grid.dy * grid.dz

    if params.lad_model == "palm_extinction":
        if lai_set:
            lad_tmp = _lad_field_palm_extinction(params, X, Y, Z, meta, lad_max=1.0)
            crown = lad_tmp > 0.0

            lai_current = float(lad_tmp.sum() * dV / A_proj)

            if lai_current <= 0:
                raise ValueError("palm_extinction produced LAI_current<=0 (check geometry/parameters).")

            scale = float(params.lai) / lai_current
            lad = lad_tmp * scale
            lad_max = float(lad.max())   # actual peak in the discrete field
            lai = float(params.lai)

        else:
            lad_max = float(params.lad_max)
            lad = _lad_field_palm_extinction(params, X, Y, Z, meta, lad_max=lad_max)
            crown = lad > 0.0
            lai = float(lad.sum() * dV / A_proj)
            scale = lad_max

        # Extended trunk for BAD: BAD=1.0 from z=0 to crown centre (mid-crown)
        # Only resolved if trunk diameter >= one grid cell; otherwise skip trunk BAD.
        crown_center_z = 0.5 * (meta["crown_base_z"] + meta["crown_top_z"])
        if float(params.trunk_diameter) >= float(grid.dx):
            r_xy = np.sqrt(X**2 + Y**2)
            extended_trunk = (r_xy <= meta["Rt"]) & (Z >= 0.0) & (Z <= crown_center_z)
        else:
            extended_trunk = np.zeros(lad.shape, dtype=bool)
        # BAD in crown is INVERSE to LAD (normalized): 0 at outer surface, bad_lad_ratio at interior
        # bad_lad_ratio = max crown BAD value (m²/m³); norm = 1 - lad/lad_max
        if float(lad_max) > 0.0:
            bad_crown = np.where(
                crown & ~extended_trunk,
                float(params.bad_lad_ratio) * np.maximum(0.0, 1.0 - lad / float(lad_max)),
                0.0,
            )
        else:
            bad_crown = np.zeros_like(lad)
        bad = np.where(extended_trunk, 1.0, bad_crown)

        return {
            "lad": lad,
            "bad": bad,
            "crown_mask": crown,
            "trunk_mask": trunk,
            "meta": meta,
            "coords": {"x": x, "y": y, "z": z},
            "params": params,
            "grid": grid,
            "profile": {
                "method": "palm_extinction",
                "k": float(params.palm_extinction_k),
            },
            "scaling": {
                "lai": float(lai),
                "lad_max": float(lad_max),
                "scale": float(scale),
            },
        }

    # -------------------------
    # Default: beta_density (with density/geometry mode)
    # -------------------------
    scaling = _compute_scaling(params, meta)
    h_c = meta["crown_height"]
    crown_base_z = meta["crown_base_z"]

    if params.profile_mode == "geometry":
        crown = _crown_mask_from_profile_geometry(params, X, Y, Z, meta)
        LAD0 = scaling["scale"]
        lad = np.where(crown, LAD0, 0.0)
    else:
        crown = _crown_mask_shape_density(params, X, Y, Z, meta)
        zeta = (Z - crown_base_z) / max(h_c, 1e-12)
        f = _beta_pdf_zeta(np.clip(zeta, 0.0, 1.0), params.alpha, params.beta)
        f = np.where((zeta >= 0.0) & (zeta <= 1.0), f, 0.0)
        S = scaling["scale"]
        lad = np.where(crown, S * f, 0.0)

    # Extended trunk for BAD: BAD=1.0 from z=0 to crown centre (mid-crown)
    # Only resolved if trunk diameter >= one grid cell; otherwise skip trunk BAD.
    crown_center_z = 0.5 * (meta["crown_base_z"] + meta["crown_top_z"])
    if float(params.trunk_diameter) >= float(grid.dx):
        r_xy = np.sqrt(X**2 + Y**2)
        extended_trunk = (r_xy <= meta["Rt"]) & (Z >= 0.0) & (Z <= crown_center_z)
    else:
        extended_trunk = np.zeros(lad.shape, dtype=bool)
    # BAD in crown proportional to LAD (normalized): 0 at interior, bad_lad_ratio at outer peak
    # bad_lad_ratio = max crown BAD value (m²/m³)
    _lad_max_beta = float(lad.max())
    if _lad_max_beta > 0.0:
        bad = np.where(extended_trunk, 1.0,
                       np.where(crown & ~extended_trunk,
                                float(params.bad_lad_ratio) * lad / _lad_max_beta, 0.0))
    else:
        bad = np.where(extended_trunk, 1.0, 0.0)

    return {
        "lad": lad,
        "bad": bad,
        "crown_mask": crown,
        "trunk_mask": trunk,
        "meta": meta,
        "coords": {"x": x, "y": y, "z": z},
        "params": params,
        "grid": grid,
        "profile": {
            "method": "beta_pdf",
            "mode": params.profile_mode,
            "alpha": float(params.alpha),
            "beta": float(params.beta),
        },
        "scaling": scaling,
    }
