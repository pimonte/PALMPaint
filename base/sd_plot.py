"""Analysis and plotting dialog for PALMPaint static drivers.

Uses matplotlib embedded via FigureCanvasTkAgg.  Requires matplotlib;
gracefully disabled when it is not installed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches
    import matplotlib.cm as _cm
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from base.surface_config import SURFACE_CONFIG
from base.building_config import BUILDING_CONFIG
from base.gridmodel import GridModel


_PLOT_TYPES = [
    "XY – simplified landcover",
    "XY – pavement types",
    "XY – vegetation types",
    "XY – LAD (column max)",
    "XY – terrain height (zt)",
    "XY – soil types",
    "XY – building types",
    "XY – building heights",
    "Cross-section",
    "Building height histogram",
    "LAD vertical profile",
    "Plan area fractions",
]

_UNITS = ["Gridboxes", "Meters", "Meters from origin"]

class SDPlotDialog(tk.Toplevel):
    """Embedded-matplotlib dialog exposing analysis plots for the current model."""

    def __init__(self, parent: tk.Widget, model: GridModel, georef) -> None:
        super().__init__(parent)
        self.title("Analysis Plots")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self._model = model
        self._georef = georef

        self._units_var = tk.StringVar(value=_UNITS[0])
        self._section_axis_var = tk.StringVar(value="N-S")
        self._slice_var = tk.IntVar(value=0)
        self._add_water_var = tk.BooleanVar(value=False)
        self._add_pavement_var = tk.BooleanVar(value=False)
        self._add_resolved_veg_var = tk.BooleanVar(value=False)
        self._add_buildings_var = tk.BooleanVar(value=False)

        self._section_frame: ttk.LabelFrame | None = None
        self._veg_option_frame: ttk.LabelFrame | None = None
        self._slice_spin: ttk.Spinbox | None = None

        self._fig = None
        self._canvas = None

        self._build_ui()
        self.after(100, self._refresh)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=6)
        left.grid(row=0, column=0, sticky="nsew")
        self._build_left_panel(left)

        right = ttk.Frame(self, padding=4)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self._build_canvas(right)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Plot type:").pack(anchor="w")

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill="x", pady=(0, 8))
        sb = ttk.Scrollbar(list_frame, orient="vertical")
        self._listbox = tk.Listbox(
            list_frame,
            yscrollcommand=sb.set,
            selectmode="single",
            exportselection=False,
            width=28,
            height=len(_PLOT_TYPES),
        )
        sb.config(command=self._listbox.yview)
        self._listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for name in _PLOT_TYPES:
            self._listbox.insert("end", name)
        self._listbox.selection_set(0)
        self._listbox.bind("<<ListboxSelect>>", self._on_listbox_change)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=4)

        ttk.Label(parent, text="Axis units:").pack(anchor="w")
        for u in _UNITS:
            ttk.Radiobutton(
                parent, text=u, variable=self._units_var, value=u,
                command=self._refresh,
            ).pack(anchor="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=4)

        # Cross-section options (shown/hidden conditionally)
        self._section_frame = ttk.LabelFrame(parent, text="Cross-section", padding=4)
        ttk.Label(self._section_frame, text="Axis:").pack(anchor="w")
        for axis_name in ("N-S", "W-E"):
            ttk.Radiobutton(
                self._section_frame, text=axis_name,
                variable=self._section_axis_var, value=axis_name,
                command=self._on_section_axis_change,
            ).pack(anchor="w")
        ttk.Label(self._section_frame, text="Slice index:").pack(anchor="w", pady=(4, 0))
        self._slice_spin = ttk.Spinbox(
            self._section_frame, textvariable=self._slice_var,
            from_=0, to=max(self._model.nx, self._model.ny) - 1,
            width=6, command=self._refresh,
        )
        self._slice_spin.pack(anchor="w")
        self._slice_spin.bind("<Return>", lambda _: self._refresh())

        # Vegetation options (shown/hidden conditionally)
        self._veg_option_frame = ttk.LabelFrame(parent, text="Vegetation options", padding=4)
        ttk.Checkbutton(
            self._veg_option_frame, text="Also show water types",
            variable=self._add_water_var, command=self._refresh,
        ).pack(anchor="w")
        ttk.Checkbutton(
            self._veg_option_frame, text="Also show pavement types",
            variable=self._add_pavement_var, command=self._refresh,
        ).pack(anchor="w")
        ttk.Checkbutton(
            self._veg_option_frame, text="Also show resolved vegetation",
            variable=self._add_resolved_veg_var, command=self._refresh,
        ).pack(anchor="w")
        ttk.Checkbutton(
            self._veg_option_frame, text="Also show building types",
            variable=self._add_buildings_var, command=self._refresh,
        ).pack(anchor="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=4)
        ttk.Button(parent, text="Export…", command=self._export).pack(anchor="w")

        self._update_option_panels()

    def _build_canvas(self, parent: ttk.Frame) -> None:
        if MATPLOTLIB_AVAILABLE:
            self._fig = Figure(figsize=(9, 7), dpi=90, layout="constrained")
            self._canvas = FigureCanvasTkAgg(self._fig, master=parent)
            self._canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        else:
            ttk.Label(
                parent,
                text="Install matplotlib to enable plots.\n\npip install matplotlib",
                justify="center",
                foreground="#888",
            ).grid(row=0, column=0)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_listbox_change(self, _event=None) -> None:
        self._update_option_panels()
        self._refresh()

    def _on_section_axis_change(self) -> None:
        m = self._model
        limit = (m.ny if self._section_axis_var.get() == "N-S" else m.nx) - 1
        self._slice_spin.config(to=limit)
        if self._slice_var.get() > limit:
            self._slice_var.set(limit)
        self._refresh()

    def _update_option_panels(self) -> None:
        sel = self._selected_plot()
        if sel == "Cross-section":
            self._section_frame.pack(fill="x", pady=(0, 4))
        else:
            self._section_frame.pack_forget()
        if sel == "XY – vegetation types":
            self._veg_option_frame.pack(fill="x", pady=(0, 4))
        else:
            self._veg_option_frame.pack_forget()

    def _selected_plot(self) -> str:
        sel = self._listbox.curselection()
        return _PLOT_TYPES[sel[0]] if sel else _PLOT_TYPES[0]

    # ------------------------------------------------------------------
    # Core refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        if self._fig is None:
            return
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        dispatch = {
            "XY – simplified landcover": self._plot_xy_simplified,
            "XY – pavement types": self._plot_xy_pavement,
            "XY – vegetation types": self._plot_xy_vegetation,
            "XY – LAD (column max)": self._plot_xy_lad,
            "XY – terrain height (zt)": self._plot_xy_zt,
            "XY – soil types": self._plot_xy_soil,
            "XY – building types": self._plot_xy_building_types,
            "XY – building heights": self._plot_xy_building_heights,
            "Cross-section": self._plot_cross_section,
            "Building height histogram": self._plot_building_histogram,
            "LAD vertical profile": self._plot_lad_profile,
            "Plan area fractions": self._plot_plan_fractions,
        }
        try:
            dispatch[self._selected_plot()](ax)
        except Exception as exc:
            ax.text(
                0.5, 0.5, f"Error: {exc}",
                transform=ax.transAxes, ha="center", va="center",
                color="red", wrap=True,
            )
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # LAD masking helper
    # ------------------------------------------------------------------

    @staticmethod
    def _lad_masked(lad_arr):
        """Return a masked array with fill values excluded.

        LAD fill can be 0 (PALMPaint default) or large positive values
        (e.g. CF _FillValue 9.96921e+36) written by get_3d_data when the
        NetCDF cell is masked.  Valid LAD is always > 0 and physically
        bounded well below 1e6 m² m⁻³, so both cases are caught by:
            mask = (arr <= 0) | (arr > 1e6)
        """
        arr = np.asarray(lad_arr, dtype=float)
        return np.ma.masked_where((arr <= 0) | (arr > 1e6), arr)

    # ------------------------------------------------------------------
    # Coordinate / extent helpers
    # ------------------------------------------------------------------

    def _xy_extent(self):
        """Return imshow extent [left, right, bottom, top] in chosen units.

        Axes follow PALM convention: x = west→east, y = south→north.
        """
        m = self._model
        nx, ny, res = m.nx, m.ny, m.res
        u = self._units_var.get()
        if u == "Gridboxes":
            return [0, nx, 0, ny]
        if u == "Meters":
            return [0.0, nx * res, 0.0, ny * res]
        ox, oy = self._georef.origin_x, self._georef.origin_y
        return [ox, ox + nx * res, oy, oy + ny * res]

    def _horiz_coords(self, n: int, axis: str = "x"):
        """Cell-centre coordinates for n gridboxes along x or y."""
        u = self._units_var.get()
        res = self._model.res
        if u == "Gridboxes":
            return np.arange(n, dtype=float) + 0.5
        coords = (np.arange(n, dtype=float) + 0.5) * res
        if u == "Meters from origin":
            coords += self._georef.origin_x if axis == "x" else self._georef.origin_y
        return coords

    def _z_coords(self, nz: int):
        """Cell-centre z coordinates for nz levels."""
        u = self._units_var.get()
        zlad = self._model.resolved_vegetation.get("zlad")
        if zlad is not None and len(zlad) == nz:
            z = np.asarray(zlad, dtype=float)
            if u == "Gridboxes":
                return np.arange(nz, dtype=float) + 0.5
            return z
        dz = self._model.dz
        if u == "Gridboxes":
            return np.arange(nz, dtype=float) + 0.5
        return (np.arange(nz, dtype=float) + 0.5) * dz

    def _axis_label_x(self) -> str:
        u = self._units_var.get()
        return "x (gridboxes)" if u == "Gridboxes" else ("x (m)" if u == "Meters" else "Easting (m)")

    def _axis_label_y(self) -> str:
        u = self._units_var.get()
        return "y (gridboxes)" if u == "Gridboxes" else ("y (m)" if u == "Meters" else "Northing (m)")

    def _z_label(self) -> str:
        return "z (gridboxes)" if self._units_var.get() == "Gridboxes" else "z (m)"

    # ------------------------------------------------------------------
    # Categorical imshow helper
    # ------------------------------------------------------------------

    def _categorical_imshow(self, ax, arr, type_dict: dict):
        """imshow for a categorical integer array using colors from type_dict.

        Uses origin='lower' so that array row 0 (= south in the model)
        appears at the bottom of the plot.  Returns legend handles for types present.
        """
        type_ids = sorted(type_dict.keys())
        colors = [type_dict[t]["display"]["color"] for t in type_ids]
        cmap = mcolors.ListedColormap(colors)
        n = len(type_ids)
        id_to_idx = {t: float(i) for i, t in enumerate(type_ids)}

        idx_arr = np.full(arr.shape, np.nan, dtype=float)
        for t, i in id_to_idx.items():
            idx_arr[arr == t] = i
        idx_ma = np.ma.masked_invalid(idx_arr)

        ax.imshow(
            idx_ma, origin="lower", cmap=cmap, vmin=-0.5, vmax=n - 0.5,
            extent=self._xy_extent(), aspect="equal", interpolation="nearest",
        )
        return [
            mpatches.Patch(color=colors[i], label=type_dict[t]["label"])
            for i, t in enumerate(type_ids)
            if (arr == t).any()
        ]

    def _add_legend(self, ax, handles: list, **kwargs) -> None:
        if handles:
            ax.legend(
                handles=handles,
                loc="upper left",
                bbox_to_anchor=(1.01, 1.0),
                borderaxespad=0,
                fontsize="small",
                **kwargs,
            )

    # ------------------------------------------------------------------
    # XY map plots
    # ------------------------------------------------------------------

    def _plot_xy_simplified(self, ax) -> None:
        m = self._model
        IF = GridModel.INT_FILL
        BF = GridModel.BUILDING_ID_FILL

        cat = np.zeros((m.ny, m.nx), dtype=np.int8)
        cat[m.vegetation_type != IF] = 1
        cat[(m.vegetation_type != IF) & (m.vegetation_type == 1)] = 6
        cat[m.water_type != IF] = 4
        cat[m.pavement_type != IF] = 3
        cat[m.building_id != BF] = 5
        lad = m.resolved_vegetation.get("lad")
        if lad is not None:
            cat[self._lad_masked(lad).max(axis=0).filled(0) > 0] = 2
        
        
        
        

        labels = ["bare", "vegetation", "resolved veg.", "pavement", "water", "building", "bare soil"]
        colors = ["#f0f0f0", "green", "darkgreen", "gray", "royalblue", "black", "#8c564b"]
        cmap = mcolors.ListedColormap(colors)
        ax.imshow(
            cat, origin="lower", cmap=cmap, vmin=-0.5, vmax=6.5,
            extent=self._xy_extent(), aspect="equal", interpolation="none",
        )
        present = sorted(set(cat.flat))
        self._add_legend(ax, [mpatches.Patch(color=colors[v], label=labels[v]) for v in present])
        ax.set_title("Simplified landcover")
        ax.set_xlabel(self._axis_label_x())
        ax.set_ylabel(self._axis_label_y())

    def _plot_xy_pavement(self, ax) -> None:
        handles = self._categorical_imshow(ax, self._model.pavement_type,
                                           SURFACE_CONFIG["pavement"]["types"])
        self._add_legend(ax, handles)
        ax.set_title("Pavement types")
        ax.set_xlabel(self._axis_label_x())
        ax.set_ylabel(self._axis_label_y())

    def _plot_xy_vegetation(self, ax) -> None:
        m = self._model
        veg_dict = SURFACE_CONFIG["vegetation"]["types"]
        water_dict = SURFACE_CONFIG["water"]["types"]
        pav_dict = SURFACE_CONFIG["pavement"]["types"]
        bld_dict = BUILDING_CONFIG["types"]

        include_water = self._add_water_var.get()
        include_pavement = self._add_pavement_var.get()
        include_resolved = self._add_resolved_veg_var.get()
        include_buildings = self._add_buildings_var.get()

        if not any((include_water, include_pavement, include_resolved, include_buildings)):
            handles = self._categorical_imshow(ax, m.vegetation_type, veg_dict)
            title = "Vegetation types"
        else:
            # Build one indexed overlay so optional layers can be appended consistently.
            layers = [
                {
                    "ids": sorted(veg_dict.keys()),
                    "values": m.vegetation_type,
                    "label_map": {t: veg_dict[t]["label"] for t in veg_dict},
                    "color_map": {t: veg_dict[t]["display"]["color"] for t in veg_dict},
                }
            ]
            title_parts = ["Vegetation"]

            if include_water:
                layers.append(
                    {
                        "ids": sorted(water_dict.keys()),
                        "values": m.water_type,
                        "label_map": {t: water_dict[t]["label"] for t in water_dict},
                        "color_map": {t: water_dict[t]["display"]["color"] for t in water_dict},
                    }
                )
                title_parts.append("water")

            if include_pavement:
                layers.append(
                    {
                        "ids": sorted(pav_dict.keys()),
                        "values": m.pavement_type,
                        "label_map": {t: pav_dict[t]["label"] for t in pav_dict},
                        "color_map": {t: pav_dict[t]["display"]["color"] for t in pav_dict},
                    }
                )
                title_parts.append("pavement")

            if include_resolved:
                lad = m.resolved_vegetation.get("lad")
                if lad is not None:
                    resolved_mask = self._lad_masked(lad).max(axis=0).filled(0) > 0
                    layers.append(
                        {
                            "ids": [1],
                            "values": resolved_mask.astype(np.int8),
                            "label_map": {1: "Resolved vegetation"},
                            "color_map": {1: "darkgreen"},
                        }
                    )
                    title_parts.append("resolved vegetation")

            if include_buildings:
                layers.append(
                    {
                        "ids": sorted(bld_dict.keys()),
                        "values": m.building_type,
                        "label_map": {t: bld_dict[t]["label"] for t in bld_dict},
                        "color_map": {t: bld_dict[t]["display"]["color"] for t in bld_dict},
                    }
                )
                title_parts.append("building types")

            idx_arr = np.full((m.ny, m.nx), np.nan, dtype=float)
            all_colors = []
            handles = []
            offset = 0
            for layer in layers:
                for j, type_id in enumerate(layer["ids"]):
                    idx = offset + j
                    idx_arr[layer["values"] == type_id] = float(idx)
                    if (layer["values"] == type_id).any():
                        handles.append(
                            mpatches.Patch(
                                color=layer["color_map"][type_id],
                                label=layer["label_map"][type_id],
                            )
                        )
                all_colors.extend(layer["color_map"][type_id] for type_id in layer["ids"])
                offset += len(layer["ids"])

            idx_ma = np.ma.masked_invalid(idx_arr)
            cmap = mcolors.ListedColormap(all_colors)
            ax.imshow(
                idx_ma, origin="lower", cmap=cmap, vmin=-0.5, vmax=len(all_colors) - 0.5,
                extent=self._xy_extent(), aspect="equal", interpolation="nearest",
            )
            title = " + ".join(title_parts) + " types"

        self._add_legend(ax, handles)
        ax.set_title(title)
        ax.set_xlabel(self._axis_label_x())
        ax.set_ylabel(self._axis_label_y())

    def _plot_xy_lad(self, ax) -> None:
        lad = self._model.resolved_vegetation.get("lad")
        if lad is None:
            ax.text(0.5, 0.5, "No LAD data loaded.", transform=ax.transAxes,
                    ha="center", va="center")
            return
        col_max = self._lad_masked(lad).max(axis=0)
        im = ax.imshow(
            col_max, origin="lower", cmap="viridis",
            extent=self._xy_extent(), aspect="equal", interpolation="nearest",
        )
        self._fig.colorbar(im, ax=ax, label="LAD max (m² m⁻³)")
        ax.set_title("LAD – column maximum")
        ax.set_xlabel(self._axis_label_x())
        ax.set_ylabel(self._axis_label_y())

    def _plot_xy_zt(self, ax) -> None:
        im = ax.imshow(
            self._model.zt, origin="lower", cmap="terrain",
            extent=self._xy_extent(), aspect="equal", interpolation="nearest",
        )
        self._fig.colorbar(im, ax=ax, label="Terrain height (m)")
        ax.set_title("Terrain height (zt)")
        ax.set_xlabel(self._axis_label_x())
        ax.set_ylabel(self._axis_label_y())

    def _plot_xy_soil(self, ax) -> None:
        handles = self._categorical_imshow(ax, self._model.soil_type,
                                           SURFACE_CONFIG["soil"]["types"])
        self._add_legend(ax, handles)
        ax.set_title("Soil types")
        ax.set_xlabel(self._axis_label_x())
        ax.set_ylabel(self._axis_label_y())

    def _plot_xy_building_types(self, ax) -> None:
        bt_dict = BUILDING_CONFIG["types"]
        handles = self._categorical_imshow(ax, self._model.building_type, bt_dict)
        self._add_legend(ax, handles)
        ax.set_title("Building types")
        ax.set_xlabel(self._axis_label_x())
        ax.set_ylabel(self._axis_label_y())

    def _plot_xy_building_heights(self, ax) -> None:
        bh = self._model.building_height
        bh_ma = np.ma.masked_where(
            (bh == GridModel.FLOAT_FILL) | (bh < 0), bh)
        im = ax.imshow(
            bh_ma, origin="lower", cmap="Reds",
            extent=self._xy_extent(), aspect="equal", interpolation="nearest",
        )
        self._fig.colorbar(im, ax=ax, label="Building height (m)")
        ax.set_title("Building heights")
        ax.set_xlabel(self._axis_label_x())
        ax.set_ylabel(self._axis_label_y())

    # ------------------------------------------------------------------
    # Cross-section
    # ------------------------------------------------------------------

    def _plot_cross_section(self, ax) -> None:
        m = self._model
        axis = self._section_axis_var.get()
        slice_idx = self._slice_var.get()
        u = self._units_var.get()

        lad_vol = m.resolved_vegetation.get("lad")

        if axis == "N-S":
            j = min(slice_idx, m.nx - 1)
            # rows 0..ny-1 in array, row 0 = north; flip so south is left
            zt_slice = m.zt[::-1, j]
            bh_slice = m.building_height[::-1, j]
            lad_2d = lad_vol[:, ::-1, j] if lad_vol is not None else None
            n_horiz = m.ny
            horiz = self._horiz_coords(n_horiz, axis="y")
            horiz_lbl = "y – S→N"
            title = f"Cross-section N–S (x col {j})"
        else:
            i_arr = min(m.ny - 1 - slice_idx, m.ny - 1)
            zt_slice = m.zt[i_arr, :]
            bh_slice = m.building_height[i_arr, :]
            lad_2d = lad_vol[:, i_arr, :] if lad_vol is not None else None
            n_horiz = m.nx
            horiz = self._horiz_coords(n_horiz, axis="x")
            horiz_lbl = "x – W→E"
            title = f"Cross-section W–E (y row {slice_idx})"

        dz = m.dz

        # Convert heights to display units
        if u == "Gridboxes":
            zt_disp = zt_slice / dz
            bh_disp = np.where(
                bh_slice == GridModel.FLOAT_FILL, 0.0, bh_slice / dz)
        else:
            zt_disp = zt_slice.astype(float)
            bh_disp = np.where(
                bh_slice == GridModel.FLOAT_FILL, 0.0, bh_slice.astype(float))

        # Terrain
        ax.fill_between(horiz, 0, zt_disp, color="#a07040", label="terrain", step="mid")

        # Buildings
        bld_top = zt_disp + bh_disp
        has_bld = bh_disp > 0
        if has_bld.any():
            ax.fill_between(
                horiz,
                np.where(has_bld, zt_disp, np.nan),
                np.where(has_bld, bld_top, np.nan),
                color="#555555", label="buildings", step="mid",
            )

        # LAD via imshow (fast, no per-cell loop)
        if lad_2d is not None:
            nz = lad_2d.shape[0]
            z = self._z_coords(nz)
            lad_ma = self._lad_masked(lad_2d)

            dz_disp = (z[1] - z[0]) if nz > 1 else (1.0 if u == "Gridboxes" else dz)
            dx_disp = (horiz[1] - horiz[0]) if n_horiz > 1 else (
                1.0 if u == "Gridboxes" else m.res)
            z_bot = z[0] - dz_disp / 2
            z_top = z[-1] + dz_disp / 2
            x_left = horiz[0] - dx_disp / 2
            x_right = horiz[-1] + dx_disp / 2

            im = ax.imshow(
                lad_ma, origin="lower", cmap="Greens",
                extent=[x_left, x_right, z_bot, z_top],
                aspect="auto", interpolation="nearest",
                alpha=0.85,
            )
            self._fig.colorbar(im, ax=ax, label="LAD (m² m⁻³)", shrink=0.6)

        ax.set_title(title)
        ax.set_xlabel(horiz_lbl + (" (gridboxes)" if u == "Gridboxes" else " (m)"))
        ax.set_ylabel(self._z_label())
        ax.legend(loc="upper right", fontsize="small")
        ax.set_xlim(horiz[0] - (horiz[1] - horiz[0]) / 2 if n_horiz > 1 else horiz[0] - 0.5,
                    horiz[-1] + (horiz[-1] - horiz[-2]) / 2 if n_horiz > 1 else horiz[-1] + 0.5)
        ax.set_ylim(bottom=0)

    # ------------------------------------------------------------------
    # Statistical / profile plots
    # ------------------------------------------------------------------

    def _plot_building_histogram(self, ax) -> None:
        bh = self._model.building_height
        valid = bh[(bh != GridModel.FLOAT_FILL) & (bh > 0)]
        if valid.size == 0:
            ax.text(0.5, 0.5, "No building heights in this domain.",
                    transform=ax.transAxes, ha="center", va="center")
            return
        ax.hist(valid, bins=30, color="firebrick", edgecolor="white", linewidth=0.4)
        ax.set_xlabel("Building height (m)")
        ax.set_ylabel("Count (grid cells)")
        ax.set_title("Building height distribution")

    def _plot_lad_profile(self, ax) -> None:
        lad = self._model.resolved_vegetation.get("lad")
        if lad is None:
            ax.text(0.5, 0.5, "No LAD data loaded.", transform=ax.transAxes,
                    ha="center", va="center")
            return
        lad_ma = self._lad_masked(lad)
        # Mean over vegetated cells only; unfilled levels get 0.
        lad_mean = lad_ma.mean(axis=(1, 2)).filled(0.0)
        z = self._z_coords(len(lad_mean))
        dz_disp = (z[1] - z[0]) * 0.8 if len(z) > 1 else 0.8
        ax.barh(z, lad_mean, height=dz_disp,
                color="forestgreen", edgecolor="white", linewidth=0.3)
        ax.set_xlabel("LAD – mean over vegetated cells (m² m⁻³)")
        ax.set_ylabel(self._z_label())
        ax.set_title("LAD vertical profile")

    def _plot_plan_fractions(self, ax) -> None:
        m = self._model
        IF = GridModel.INT_FILL
        BF = GridModel.BUILDING_ID_FILL
        total = m.nx * m.ny

        n_bld = int((m.building_id != BF).sum())
        n_pav = int((m.pavement_type != IF).sum())
        n_veg = int((m.vegetation_type != IF).sum())
        n_wat = int((m.water_type != IF).sum())
        lad = m.resolved_vegetation.get("lad")
        n_rv = int((self._lad_masked(lad).max(axis=0).filled(0) > 0).sum()) if lad is not None else 0

        labels = ["Building", "Pavement", "Vegetation", "Water", "Resolved veg."]
        counts = [n_bld, n_pav, n_veg, n_wat, n_rv]
        colors = ["firebrick", "gray", "green", "royalblue", "darkgreen"]

        fracs = [c / total * 100.0 for c in counts]
        present = [(l, f, c) for l, f, c in zip(labels, fracs, colors) if f > 0]
        if not present:
            ax.text(0.5, 0.5, "No surface data in this domain.",
                    transform=ax.transAxes, ha="center", va="center")
            return
        lbls, fs, cs = zip(*present)
        bars = ax.bar(lbls, fs, color=cs, edgecolor="white")
        ax.set_ylabel("Plan area fraction (%)")
        ax.set_title("Surface type coverage")
        ax.set_ylim(0, max(fs) * 1.18)
        for bar, f in zip(bars, fs):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(fs) * 0.01,
                f"{f:.1f}%", ha="center", va="bottom", fontsize="small",
            )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export(self) -> None:
        if self._fig is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("PDF document", "*.pdf"),
                ("SVG vector", "*.svg"),
                ("All files", "*.*"),
            ],
            initialfile="analysis_plot.png",
            parent=self,
        )
        if path:
            self._fig.savefig(path, dpi=150)
