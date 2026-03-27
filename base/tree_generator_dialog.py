"""
tree_generator_dialog.py

Tkinter dialog for configuring TreeParams and generating realistic 3D LAD tree fields.

The dialog is always accessible regardless of whether matplotlib is installed.
Matplotlib is only needed for the live preview panel — if it is absent the panel
shows an informational hint instead.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from base.tree_generator_core import generate_tree, TreeParams, Grid

PRESETS_DIR = Path.home() / ".config" / "palmpaint" / "presets"

# PALM Kronenform-IDs → Anzeigebeschriftung
_SHAPE_LABELS = {
    1: "1 - Spherical",
    2: "2 - Cylindrical",
    3: "3 - Conical",
    4: "4 - Inv. Conical",
    5: "5 - Paraboloid",
    6: "6 - Inv. Paraboloid",
}
_SHAPE_DISPLAY_VALUES = list(_SHAPE_LABELS.values())
# PALM extinction defaults per crown shape: k_sphere (shape 1) / k_cone (shapes 2-6)
_SHAPE_DEFAULT_K = {1: 0.6, 2: 0.2, 3: 0.2, 4: 0.2, 5: 0.2, 6: 0.2}
# Backward compatibility: old string names → PALM int
_SHAPE_STR_COMPAT = {
    "ellipsoid": 1, "cylinder": 2, "cone": 3,
    "inverted_cone": 4, "paraboloid": 5, "inverted_paraboloid": 6,
}

# Profile modes: internal key → display label
_PROFILE_LABELS = {
    "density":  "Beta / Markkanen (2003)",
    "geometry": "Geometrie (Beta-Form)",
}
_PROFILE_VALUES = {v: k for k, v in _PROFILE_LABELS.items()}

# Default parameter values shown when the dialog opens
_DEFAULTS = dict(
    max_tree_height=12.0,
    crown_diameter=4.0,
    crown_ratio=1.0,          # crown_height / crown_diameter (PALM-Konvention)
    trunk_diameter=0.35,
    crown_shape=1,            # PALM shape ID: 1 = Ellipsoid
    alpha=5.0,
    beta=3.0,
    lai_lad_choice="lai",
    lai=3.0,
    lad_max=1.0,
    profile_mode="density",
    lad_model="palm_extinction",
    palm_extinction_k=0.6,   # PALM default k_sphere (Shape 1 = Ellipsoid)
    bad_lad_ratio=0.5,
)


class TreeGeneratorDialog(tk.Toplevel):
    """Modal-ish dialog for configuring and previewing tree generator parameters.

    Parameters
    ----------
    parent : tk.Widget
        Parent widget (usually the main application window).
    on_apply_callback : callable
        Called with a ``dict`` matching the ``TreeParams`` keyword arguments
        (lai or lad_max set, the other is None) when the user clicks
        "Apply to Brush".
    """

    def __init__(self, parent: tk.Widget, on_apply_callback=None, get_grid_config=None):
        super().__init__(parent)
        self.title("Tree Generator (alpha)")
        self.resizable(True, True)
        self.on_apply_callback = on_apply_callback
        self._get_grid_config = get_grid_config  # callable () -> (dx, dy, dz), or None
        self._colorbar = None  # shared colorbar, recreated on each preview

        # Suppress destroy — just hide
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self._build_vars()
        self._build_ui()

        # Initial preview if matplotlib available
        if MATPLOTLIB_AVAILABLE:
            self.after(100, self._update_preview)

    # ------------------------------------------------------------------
    # Tk variable initialisation
    # ------------------------------------------------------------------

    def _build_vars(self):
        d = _DEFAULTS
        self._v_height      = tk.DoubleVar(value=d["max_tree_height"])
        self._v_crown_d     = tk.DoubleVar(value=d["crown_diameter"])
        self._v_aspect      = tk.DoubleVar(value=d["crown_ratio"])   # stores crown_ratio
        self._v_trunk_d     = tk.DoubleVar(value=d["trunk_diameter"])
        self._v_crown_shape = tk.StringVar(value=_SHAPE_LABELS[d["crown_shape"]])
        self._v_alpha       = tk.DoubleVar(value=d["alpha"])
        self._v_beta        = tk.DoubleVar(value=d["beta"])
        self._v_lai_lad     = tk.StringVar(value=d["lai_lad_choice"])
        self._v_lai         = tk.DoubleVar(value=d["lai"])
        self._v_lad_max     = tk.DoubleVar(value=d["lad_max"])
        self._v_profile     = tk.StringVar(value=_PROFILE_LABELS[d["profile_mode"]])
        self._v_lad_model   = tk.StringVar(value=d["lad_model"])
        self._v_ext_k       = tk.DoubleVar(value=d["palm_extinction_k"])
        self._v_bad_ratio   = tk.DoubleVar(value=d["bad_lad_ratio"])
        # Traces to enable/disable dependent controls
        self._v_lad_model.trace_add("write", lambda *_: self._on_lad_model_change())
        self._v_crown_shape.trace_add("write", lambda *_: self._on_shape_change())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)

        # Left: parameter controls
        left = ttk.LabelFrame(outer, text="Tree Parameters", padding=6)
        left.pack(side="left", fill="y", padx=(0, 6))
        self._build_params(left)

        # Right: preview + action buttons
        right_col = ttk.Frame(outer)
        right_col.pack(side="left", fill="both", expand=True)

        self._build_preview(right_col)
        self._build_buttons(right_col)

    def _spinbox(self, parent, var, from_, to, increment, width=8):
        sb = ttk.Spinbox(parent, textvariable=var, from_=from_, to=to,
                         increment=increment, width=width)
        return sb

    def _row(self, parent, row, label_text, widget):
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", pady=2)
        widget.grid(row=row, column=1, sticky="ew", padx=(4, 0), pady=2)

    def _build_params(self, parent):
        parent.columnconfigure(1, weight=1)
        r = 0

        # Geometry
        ttk.Label(parent, text="─── Geometry ───", foreground="#555").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(0, 2))
        r += 1

        self._row(parent, r, "Max height (m):",
                  self._spinbox(parent, self._v_height, 0.5, 80.0, 0.5)); r += 1
        self._row(parent, r, "Crown diameter (m):",
                  self._spinbox(parent, self._v_crown_d, 0.5, 40.0, 0.5)); r += 1
        self._row(parent, r, "Trunk diameter (m):",
                  self._spinbox(parent, self._v_trunk_d, 0.01, 5.0, 0.01)); r += 1
        self._row(parent, r, "Crown ratio (H/D):",
                  self._spinbox(parent, self._v_aspect, 0.1, 10.0, 0.1)); r += 1
        shape_cb = ttk.Combobox(parent, textvariable=self._v_crown_shape,
                                values=_SHAPE_DISPLAY_VALUES,
                                state="readonly", width=22)
        self._row(parent, r, "Crown shape:", shape_cb); r += 1

        # LAD model
        ttk.Label(parent, text="─── LAD Model ───", foreground="#555").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(6, 2))
        r += 1

        self._row(parent, r, "LAD model:",
                  ttk.OptionMenu(parent, self._v_lad_model,
                                 self._v_lad_model.get(),
                                 "beta_density", "palm_extinction")); r += 1

        # Beta profile params (only meaningful for beta_density)
        self._profile_cb = ttk.Combobox(parent, textvariable=self._v_profile,
                                        values=list(_PROFILE_LABELS.values()),
                                        state="readonly", width=24)
        self._row(parent, r, "Profil-Modus:", self._profile_cb); r += 1
        self._alpha_sb = self._spinbox(parent, self._v_alpha, 0.1, 20.0, 0.1)
        self._row(parent, r, "Alpha (β profile):", self._alpha_sb); r += 1
        self._beta_sb = self._spinbox(parent, self._v_beta, 0.1, 20.0, 0.1)
        self._row(parent, r, "Beta (β profile):", self._beta_sb); r += 1

        # Palm extinction k (only meaningful for palm_extinction)
        self._ext_k_sb = self._spinbox(parent, self._v_ext_k, 0.1, 20.0, 0.1)
        self._row(parent, r, "Extinction k:", self._ext_k_sb); r += 1

        # Scaling
        ttk.Label(parent, text="─── Scaling ───", foreground="#555").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(6, 2))
        r += 1

        sf = ttk.Frame(parent)
        sf.grid(row=r, column=0, columnspan=2, sticky="ew"); r += 1
        ttk.Radiobutton(sf, text="LAI", variable=self._v_lai_lad, value="lai",
                        command=self._on_lailad_toggle).pack(side="left")
        ttk.Radiobutton(sf, text="LAD_max", variable=self._v_lai_lad, value="lad_max",
                        command=self._on_lailad_toggle).pack(side="left", padx=(8, 0))

        self._lai_sb = self._spinbox(parent, self._v_lai, 0.1, 100.0, 0.1)
        self._row(parent, r, "LAI (m²/m²):", self._lai_sb); r += 1

        self._ladmax_sb = self._spinbox(parent, self._v_lad_max, 0.01, 50.0, 0.01)
        self._row(parent, r, "LAD_max (m²/m³):", self._ladmax_sb); r += 1

        # BAD
        ttk.Label(parent, text="─── BAD ───", foreground="#555").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(6, 2))
        r += 1
        self._row(parent, r, "BAD/LAD ratio:",
                  self._spinbox(parent, self._v_bad_ratio, 0.0, 1.0, 0.001, width=8)); r += 1

        self._on_lailad_toggle()     # set initial enable/disable state
        self._on_lad_model_change()  # grey out alpha/beta or k based on model

    def _on_lailad_toggle(self):
        use_lai = self._v_lai_lad.get() == "lai"
        self._lai_sb.configure(state="normal" if use_lai else "disabled")
        self._ladmax_sb.configure(state="disabled" if use_lai else "normal")

    def _on_lad_model_change(self, *_):
        """Enable controls relevant to the current LAD model; grey out others."""
        if not hasattr(self, "_alpha_sb"):
            return  # widgets not yet built
        use_ext = self._v_lad_model.get() == "palm_extinction"
        beta_state = "disabled" if use_ext else "normal"
        ext_state  = "normal"   if use_ext else "disabled"
        self._alpha_sb.configure(state=beta_state)
        self._beta_sb.configure(state=beta_state)
        self._profile_cb.configure(state="disabled" if use_ext else "readonly")
        self._ext_k_sb.configure(state=ext_state)

    def _on_shape_change(self, *_):
        """Set the default extinction k for the selected shape (PALM defaults)."""
        if not hasattr(self, "_ext_k_sb"):
            return
        label = self._v_crown_shape.get()
        try:
            shape_id = int(label.split(" ")[0])
        except (ValueError, IndexError):
            shape_id = 1
        self._v_ext_k.set(_SHAPE_DEFAULT_K.get(shape_id, 0.6))

    def _build_preview(self, parent):
        preview_frame = ttk.LabelFrame(parent, text="Preview", padding=4)
        preview_frame.pack(fill="both", expand=True, pady=(0, 6))
        self._preview_frame = preview_frame

        if MATPLOTLIB_AVAILABLE:
            from matplotlib.gridspec import GridSpec
            fig = Figure(figsize=(9, 5), dpi=90, layout="constrained")
            self._fig = fig
            self._ax_profile = None
            # Layout: narrow profile column on the left, 2×3 panels on the right
            gs = GridSpec(2, 4, figure=fig, width_ratios=[0.55, 1, 1, 1])
            self._ax_profile = fig.add_subplot(gs[:, 0])
            self._axes = []
            for _r, _c in [(0, 1), (0, 2), (0, 3), (1, 1), (1, 2), (1, 3)]:
                self._axes.append(fig.add_subplot(gs[_r, _c]))
            canvas = FigureCanvasTkAgg(fig, master=preview_frame)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self._canvas = canvas
        else:
            ttk.Label(
                preview_frame,
                text="Install matplotlib for live preview.\n\n"
                     "pip install matplotlib",
                justify="center",
                foreground="#888",
            ).pack(expand=True)
            self._fig = None
            self._canvas = None

    def _build_buttons(self, parent):
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x")

        if MATPLOTLIB_AVAILABLE:
            ttk.Button(btn_frame, text="Preview",
                       command=self._update_preview).pack(side="left", padx=(0, 4))

        ttk.Button(btn_frame, text="Save Preset",
                   command=self._save_preset).pack(side="left", padx=(0, 4))
        ttk.Button(btn_frame, text="Load Preset",
                   command=self._load_preset).pack(side="left", padx=(0, 4))

        ttk.Button(btn_frame, text="Apply to Brush",
                   command=self._apply).pack(side="right")

    # ------------------------------------------------------------------
    # Preview rendering
    # ------------------------------------------------------------------

    def _build_tree_params(self) -> TreeParams:
        """Read all Tk vars and construct a TreeParams instance."""
        use_lai = self._v_lai_lad.get() == "lai"
        crown_shape = int(self._v_crown_shape.get().split(" ")[0])
        profile_mode = _PROFILE_VALUES.get(self._v_profile.get(), self._v_profile.get())
        return TreeParams(
            max_tree_height    = float(self._v_height.get()),
            crown_diameter     = float(self._v_crown_d.get()),
            trunk_diameter     = float(self._v_trunk_d.get()),
            crown_shape        = crown_shape,
            crown_ratio        = float(self._v_aspect.get()),
            alpha              = float(self._v_alpha.get()),
            beta               = float(self._v_beta.get()),
            lai                = float(self._v_lai.get()) if use_lai else None,
            lad_max            = float(self._v_lad_max.get()) if not use_lai else None,
            profile_mode       = profile_mode,
            lad_model          = self._v_lad_model.get(),
            palm_extinction_k  = float(self._v_ext_k.get()),
            bad_lad_ratio      = float(self._v_bad_ratio.get()),
        )

    def _params_as_dict(self) -> dict:
        """Return a JSON-serialisable dict matching TreeParams kwargs."""
        use_lai = self._v_lai_lad.get() == "lai"
        crown_shape = int(self._v_crown_shape.get().split(" ")[0])
        profile_mode = _PROFILE_VALUES.get(self._v_profile.get(), self._v_profile.get())
        return dict(
            max_tree_height    = float(self._v_height.get()),
            crown_diameter     = float(self._v_crown_d.get()),
            trunk_diameter     = float(self._v_trunk_d.get()),
            crown_shape        = crown_shape,
            crown_ratio        = float(self._v_aspect.get()),
            alpha              = float(self._v_alpha.get()),
            beta               = float(self._v_beta.get()),
            lai                = float(self._v_lai.get()) if use_lai else None,
            lad_max            = float(self._v_lad_max.get()) if not use_lai else None,
            profile_mode       = profile_mode,
            lad_model          = self._v_lad_model.get(),
            palm_extinction_k  = float(self._v_ext_k.get()),
            bad_lad_ratio      = float(self._v_bad_ratio.get()),
        )

    def _update_preview(self):
        if not MATPLOTLIB_AVAILABLE or self._fig is None:
            return
        try:
            params = self._build_tree_params()
            if self._get_grid_config is not None:
                dx, dy, dz = self._get_grid_config()
            else:
                dx = dy = dz = 1.0
            self._preview_frame.configure(text=f"Preview (dx={dx:g} m, dz={dz:g} m)")
            grid = Grid(dx=dx, dy=dy, dz=dz, pad_xy=0.0, pad_z=0.0)
            result = generate_tree(params, grid)
        except Exception as exc:
            for ax in self._axes:
                ax.cla()
            if self._ax_profile is not None:
                self._ax_profile.cla()
            self._axes[0].text(0.5, 0.5, str(exc), transform=self._axes[0].transAxes,
                               ha="center", va="center", wrap=True, color="red")
            self._canvas.draw()
            return

        import numpy as np
        import matplotlib.cm as mcm
        import matplotlib.colors as mcolors

        lad = result["lad"]          # shape (nz, ny, nx)
        x   = result["coords"]["x"]  # 1-D, shape (nx,)
        y   = result["coords"]["y"]  # 1-D, shape (ny,)
        z   = result["coords"]["z"]  # 1-D, shape (nz,)

        nz, ny, nx = lad.shape
        lad_max = result["scaling"]["lad_max"]
        vmin, vmax = 0.0, max(float(lad_max), 1e-9)

        cmap = mcm.get_cmap("YlGn").copy()
        cmap.set_bad(color="white")   # masked (zero) cells → white
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

        def _masked(arr):
            """Mask cells with no LAD so they show as white background."""
            return np.ma.masked_where(arr <= 0.0, arr)

        # Crown height range in z-indices
        # iz_base: first cell whose centre is inside the crown (z >= crown_base)
        # iz_top : last  cell whose centre is inside the crown (z <= crown_top)
        cb = result["meta"]["crown_base_z"]
        ct = result["meta"]["crown_top_z"]
        iz_base = max(0, int(np.searchsorted(z, cb)))
        iz_top  = min(nz - 1, max(iz_base, int(np.searchsorted(z, ct, side="right")) - 1))
        # keep iz0/iz1 with ±1 buffer only for the vertical cross-section z-limits
        iz0 = max(0, iz_base - 1)
        iz1 = min(nz - 1, iz_top + 1)

        cx = nx // 2
        cy = ny // 2

        for ax in self._axes:
            ax.cla()
            ax.set_facecolor("white")
        self._ax_profile.cla()
        self._ax_profile.set_facecolor("white")

        # Remove old colorbar before redrawing
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
            self._colorbar = None

        import numpy as np  # noqa: F811  (already imported above, harmless)

        # Extents in metres (cell edges) for imshow
        ext_xy = [x[0] - dx / 2.0, x[-1] + dx / 2.0, y[0] - dy / 2.0, y[-1] + dy / 2.0]
        ext_zx = [x[0] - dx / 2.0, x[-1] + dx / 2.0, z[0] - dz / 2.0, z[-1] + dz / 2.0]
        ext_zy = [y[0] - dy / 2.0, y[-1] + dy / 2.0, z[0] - dz / 2.0, z[-1] + dz / 2.0]

        # Axis limits with 1-cell padding on every side
        x_buf = dx
        y_buf = dy
        z_buf = dz
        x_lim = [x[0] - dx / 2.0 - x_buf, x[-1] + dx / 2.0 + x_buf]
        y_lim = [y[0] - dy / 2.0 - y_buf, y[-1] + dy / 2.0 + y_buf]
        z_lim = [max(0.0, z[0] - dz / 2.0 - z_buf), z[-1] + dz / 2.0 + z_buf]

        titles = ["Max-Z projection", "Z-X slice (centre)", "Z-Y slice (centre)"]

        # Panel 0: max-z projection (bird's eye)
        img0 = lad.max(axis=0)
        im = self._axes[0].imshow(_masked(img0), origin="lower", aspect="equal",
                             cmap=cmap, norm=norm, interpolation="nearest", extent=ext_xy)
        self._axes[0].set_xlim(x_lim)
        self._axes[0].set_ylim(y_lim)
        self._axes[0].set_title(titles[0], fontsize=7)

        # Panel 1: vertical Z-X cross-section through y-centre
        img1 = lad[:, cy, :]  # (nz, nx)
        self._axes[1].imshow(_masked(img1), origin="lower", aspect="equal",
                             cmap=cmap, norm=norm, interpolation="nearest", extent=ext_zx)
        self._axes[1].set_xlim(x_lim)
        self._axes[1].set_ylim(z_lim)
        self._axes[1].set_title(titles[1], fontsize=7)
        self._axes[1].set_xlabel("x (m)", fontsize=6)
        self._axes[1].set_ylabel("z (m)", fontsize=6)

        # Panel 2: vertical Z-Y cross-section through x-centre
        img2 = lad[:, :, cx]  # (nz, ny)
        self._axes[2].imshow(_masked(img2), origin="lower", aspect="equal",
                             cmap=cmap, norm=norm, interpolation="nearest", extent=ext_zy)
        self._axes[2].set_xlim(y_lim)
        self._axes[2].set_ylim(z_lim)
        self._axes[2].set_title(titles[2], fontsize=7)
        self._axes[2].set_xlabel("y (m)", fontsize=6)
        self._axes[2].set_ylabel("z (m)", fontsize=6)

        # Panels 3-5: horizontal XY slices evenly spread through crown height
        # Use np.linspace across the crown cell range to guarantee distinct indices
        crown_iz = np.round(np.linspace(iz_base, iz_top, 3)).astype(int)
        crown_iz = np.clip(crown_iz, 0, nz - 1)
        for pi, (frac_label, iz) in enumerate(zip(["1/3 crown", "½ crown", "2/3 crown"], crown_iz)):
            img = lad[iz, :, :]
            self._axes[3 + pi].imshow(_masked(img), origin="lower", aspect="equal",
                                       cmap=cmap, norm=norm, interpolation="nearest", extent=ext_xy)
            self._axes[3 + pi].set_xlim(x_lim)
            self._axes[3 + pi].set_ylim(y_lim)
            self._axes[3 + pi].set_title(f"XY at {frac_label}  z={z[iz]:.1f}m", fontsize=7)

        # LAD profile panel (left column)
        # lad_area: horizontal mean over ALL cells (including air) at each z.
        #   Integrating lad_area × dz × (nx*ny*dx*dy) / A_proj ≈ LAI.
        #   Shows the "effective" LAD felt by radiation crossing the canopy.
        # lad_max_z: peak LAD in any single cell — highest at the crown surface.
        lad_area  = lad.mean(axis=(1, 2))          # area-averaged per z-level
        lad_max_z = lad.max(axis=(1, 2))            # cell peak per z-level
        self._ax_profile.plot(lad_area,  z, color="#2ca02c", lw=1.5, label="Avg. area")
        self._ax_profile.plot(lad_max_z, z, color="#98df8a", lw=1.0, ls="--", label="Cell max")
        self._ax_profile.axhline(cb, color="gray", lw=0.8, ls=":", alpha=0.7,
                                  label=f"Crown  {cb:.1f}–{ct:.1f} m")
        self._ax_profile.axhline(ct, color="gray", lw=0.8, ls=":", alpha=0.7)
        self._ax_profile.set_ylim(z_lim)
        self._ax_profile.set_xlabel("LAD (m²/m³)", fontsize=6)
        self._ax_profile.set_ylabel("z (m)", fontsize=6)
        lai_val    = result["scaling"]["lai"]
        ladmax_val = result["scaling"]["lad_max"]
        self._ax_profile.set_title(
            f"LAD-Profil\nLAI={lai_val:.2f} m²/m²  |  LAD_max={ladmax_val:.2f} m²/m³",
            fontsize=6, loc="left",
        )
        self._ax_profile.tick_params(labelsize=9)
        self._ax_profile.legend(fontsize=7, loc="upper right")

        # Shared colorbar
        sm = mcm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        self._colorbar = self._fig.colorbar(
            sm, ax=self._axes, shrink=0.7, pad=0.02,
            label="LAD (m² m⁻³)", aspect=30,
        )
        self._colorbar.ax.tick_params(labelsize=9)
        self._colorbar.set_label("LAD (m² m⁻³)", fontsize=9)

        self._canvas.draw()

    # ------------------------------------------------------------------
    # Apply / Preset
    # ------------------------------------------------------------------

    def _apply(self):
        try:
            params_dict = self._params_as_dict()
            # Validate by constructing (raises if params are bad)
            TreeParams(**params_dict)
        except Exception as exc:
            messagebox.showerror("Invalid Parameters", str(exc), parent=self)
            return

        if self.on_apply_callback:
            self.on_apply_callback(params_dict)
        self.withdraw()

    def _save_preset(self):
        try:
            params_dict = self._params_as_dict()
            TreeParams(**params_dict)  # validate
        except Exception as exc:
            messagebox.showerror("Invalid Parameters", str(exc), parent=self)
            return

        PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(
            parent=self,
            initialdir=str(PRESETS_DIR),
            defaultextension=".json",
            filetypes=[("JSON preset", "*.json"), ("All files", "*.*")],
            title="Save Tree Preset",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(params_dict, f, indent=2)

    def _load_preset(self):
        path = filedialog.askopenfilename(
            parent=self,
            initialdir=str(PRESETS_DIR) if PRESETS_DIR.exists() else str(Path.home()),
            filetypes=[("JSON preset", "*.json"), ("All files", "*.*")],
            title="Load Tree Preset",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc), parent=self)
            return

        # Populate Tk vars; unknown keys are silently ignored
        if "max_tree_height"    in d: self._v_height.set(d["max_tree_height"])
        if "crown_diameter"     in d: self._v_crown_d.set(d["crown_diameter"])
        if "trunk_diameter"     in d: self._v_trunk_d.set(d["trunk_diameter"])
        # Crown shape: accept int (current) or old string names (backward compat)
        if "crown_shape" in d:
            raw = d["crown_shape"]
            if isinstance(raw, str):
                shape_id = _SHAPE_STR_COMPAT.get(raw, 1)
            else:
                shape_id = int(raw)
            self._v_crown_shape.set(_SHAPE_LABELS.get(shape_id, _SHAPE_LABELS[1]))
        # Crown ratio: accept new key or convert old crown_aspect_ratio (inverse)
        if "crown_ratio" in d:
            self._v_aspect.set(d["crown_ratio"])
        elif "crown_aspect_ratio" in d:
            old = float(d["crown_aspect_ratio"])
            self._v_aspect.set(round(1.0 / old, 4) if old != 0 else 1.0)
        if "alpha"              in d: self._v_alpha.set(d["alpha"])
        if "beta"               in d: self._v_beta.set(d["beta"])
        # Profile mode: accept internal key or old display label
        if "profile_mode" in d:
            pm = d["profile_mode"]
            self._v_profile.set(_PROFILE_LABELS.get(pm, pm))
        if "lad_model"          in d: self._v_lad_model.set(d["lad_model"])
        if "palm_extinction_k"  in d: self._v_ext_k.set(d["palm_extinction_k"])
        if "bad_lad_ratio"      in d: self._v_bad_ratio.set(d["bad_lad_ratio"])

        if d.get("lai") is not None:
            self._v_lai_lad.set("lai")
            self._v_lai.set(d["lai"])
        elif d.get("lad_max") is not None:
            self._v_lai_lad.set("lad_max")
            self._v_lad_max.set(d["lad_max"])
        self._on_lailad_toggle()

        if MATPLOTLIB_AVAILABLE:
            self._update_preview()

    # ------------------------------------------------------------------
    # Public helper — repopulate from an existing params dict
    # ------------------------------------------------------------------

    def set_params(self, params_dict: dict):
        """Populate dialog controls from an existing params dict (e.g. after undo)."""
        self._load_from_dict(params_dict)

    def _load_from_dict(self, d: dict):
        """Internal: populate Tk vars from dict (same fields as _params_as_dict)."""
        if "max_tree_height"    in d: self._v_height.set(d["max_tree_height"])
        if "crown_diameter"     in d: self._v_crown_d.set(d["crown_diameter"])
        if "trunk_diameter"     in d: self._v_trunk_d.set(d["trunk_diameter"])
        if "crown_shape" in d:
            raw = d["crown_shape"]
            if isinstance(raw, str):
                shape_id = _SHAPE_STR_COMPAT.get(raw, 1)
            else:
                shape_id = int(raw)
            self._v_crown_shape.set(_SHAPE_LABELS.get(shape_id, _SHAPE_LABELS[1]))
        if "crown_ratio" in d:
            self._v_aspect.set(d["crown_ratio"])
        elif "crown_aspect_ratio" in d:
            old = float(d["crown_aspect_ratio"])
            self._v_aspect.set(round(1.0 / old, 4) if old != 0 else 1.0)
        if "alpha"              in d: self._v_alpha.set(d["alpha"])
        if "beta"               in d: self._v_beta.set(d["beta"])
        if "profile_mode" in d:
            pm = d["profile_mode"]
            self._v_profile.set(_PROFILE_LABELS.get(pm, pm))
        if "lad_model"          in d: self._v_lad_model.set(d["lad_model"])
        if "palm_extinction_k"  in d: self._v_ext_k.set(d["palm_extinction_k"])
        if "bad_lad_ratio"      in d: self._v_bad_ratio.set(d["bad_lad_ratio"])
        if d.get("lai") is not None:
            self._v_lai_lad.set("lai")
            self._v_lai.set(d["lai"])
        elif d.get("lad_max") is not None:
            self._v_lai_lad.set("lad_max")
            self._v_lad_max.set(d["lad_max"])
        self._on_lailad_toggle()
