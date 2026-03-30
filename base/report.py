import tkinter as tk
from tkinter import Toplevel
from tkinter import filedialog
from tkinter import messagebox
from datetime import datetime
from base.gridmodel import GridModel

def format_value(value, width=10):
    """Ensures integers and floats are aligned correctly."""
    if isinstance(value, int):
        return f"{value:>{width}d}"  # Right-align integers with fixed width
    elif isinstance(value, float):
        return f"{value:>{width}.2f}"  # Right-align floats with 2 decimal places
    else:
        return str(value)  # Handle non-numeric values gracefully

def generate_report(root, pixels, nx, ny, dxy, dz, ori, resolved_vegetation=None, tree_instances=None):
    """Generate statistics and plot the domain."""
    land_use_counts = {"vegetation": 0, "pavement": 0, "soil": 0, "water": 0, "building": 0}
    total_pixels = len(pixels)

    for pixel in pixels.values():
        if pixel["vegetation_type"] > 1:
            land_use_counts["vegetation"] += 1
        elif pixel["pavement_type"] > 0:
            land_use_counts["pavement"] += 1
        elif pixel["vegetation_type"] == 1:
            land_use_counts["soil"] += 1
        elif "water_type" in pixel and pixel["water_type"] > 0:
            land_use_counts["water"] += 1
        elif "building_id" in pixel and pixel["building_id"] > 0:
            land_use_counts["building"] += 1

    percentages = {key: (value / total_pixels) * 100 for key, value in land_use_counts.items()}
    
    # Namelist Parameters
    namelist_info = f"nx: {nx-1}\n"
    namelist_info += f"ny: {ny-1}\n"
    namelist_info += f"nz: \n"
    namelist_info += f"\n"
    namelist_info += f"dx: {dxy}\n"
    namelist_info += f"dy: {dxy}\n"
    namelist_info += f"dz: {dz}\n"
    
    # Domain information
    domain_data = {
    "Number of 2D Grid Cells": format_value(total_pixels),
    "Domain size x (m)": format_value(nx * dxy),
    "Domain size y (m)": format_value(ny * dxy),
    "Grid width (m)": format_value(dxy),
    "Vertical dz (m)": format_value(dz),
    "Number of Gridpoints x": format_value(nx),
    "Number of Gridpoints y": format_value(ny),
    }
    
    geo_data = {
    "Lat": format_value(ori[0]),
    "Lon": format_value(ori[1]),
    "Projected x (m)": format_value(ori[2]),
    "Projected y (m)": format_value(ori[3]),
    }
    
    # Display Building Information
    building_info = f"Building Information\n"
    building_info += f"==================\n"
    
    # ----------------------------------------------------------------
    # Tree Information
    # ----------------------------------------------------------------
    tree_data = {}
    rv = resolved_vegetation or {}
    lad_vol = rv.get("lad")
    bad_vol = rv.get("bad")
    zlad    = rv.get("zlad")
    tid_vol = rv.get("tree_id")
    instances = tree_instances or []

    if lad_vol is not None and lad_vol.ndim == 3:
        import numpy as _np

        # dz: spacing between zlad levels (uniform assumed)
        dz = GridModel.infer_dz_from_zlad(zlad, dz)

        cell_area = float(dxy) ** 2  # m²

        # 2-D mask: any column with lad > 0
        valid_lad = lad_vol > 0
        canopy_mask = _np.any(valid_lad, axis=0)   # (ny, nx)
        canopy_cells = int(canopy_mask.sum())
        canopy_cover_m2 = canopy_cells * cell_area

        # Total leaf area (m²): sum(lad[lad>0]) * dz * cell_area
        total_leaf_area = float(lad_vol[valid_lad].sum()) * dz * cell_area

        # Unique tree IDs
        if tid_vol is not None:
            unique_ids = set(int(v) for v in tid_vol[tid_vol > 0].ravel())
        else:
            unique_ids = set()

        tree_data["Canopy cover (m\u00b2)"] = format_value(canopy_cover_m2)
        tree_data["Total leaf area (m\u00b2)"] = format_value(total_leaf_area)
        tree_data["Unique tree IDs"] = format_value(len(unique_ids))

        # BAD
        if bad_vol is not None:
            valid_bad = bad_vol[bad_vol > 0]
            if valid_bad.size > 0:
                total_ba = float(valid_bad.sum()) * dz * cell_area
                tree_data["Total branch area (m\u00b2)"] = format_value(total_ba)

        # Per-column max tree height from lad volume (works for all trees, incl. loaded)
        if zlad is not None and canopy_cells > 0:
            # For each column with lad > 0, find the highest z-level with lad > 0
            # lad_vol shape: (nz, ny, nx); canopy_mask shape: (ny, nx)
            col_max_heights = []
            rows_i, cols_i = _np.where(canopy_mask)
            for r, c in zip(rows_i, cols_i):
                nz_idx = _np.where(lad_vol[:, r, c] > 0)[0]
                if nz_idx.size > 0:
                    col_max_heights.append(float(zlad[nz_idx[-1]]))
            if col_max_heights:
                tree_data["Tree height min / avg / max (m)"] = (
                    f"{min(col_max_heights):>6.1f} / "
                    f"{sum(col_max_heights)/len(col_max_heights):>6.1f} / "
                    f"{max(col_max_heights):>6.1f}"
                )

        # Per-tree stats from tree_instances (painted trees only)
        if instances:
            crowns  = [t["crown_diameter"]  for t in instances]
            lais    = [t["lai"]             for t in instances]
            n = len(instances)
            tree_data["Painted trees"] = format_value(n)
            tree_data["Crown diameter min / avg / max (m)"] = (
                f"{min(crowns):>6.1f} / {sum(crowns)/n:>6.1f} / {max(crowns):>6.1f}"
            )
            tree_data["LAI min / avg / max"] = (
                f"{min(lais):>6.2f} / {sum(lais)/n:>6.2f} / {max(lais):>6.2f}"
            )
    else:
        tree_data["Trees detected"] = "No resolved vegetation data found"
    
    building_data = {}
    if land_use_counts["building"] > 0:
        # Collect valid building heights: exclude sentinel/missing values and require building_id > 0
        valid_heights = [
            p["building_height"]
            for p in pixels.values()
            if "building_height" in p and p.get("building_height") != -127 and p.get("building_height") >= 0
            and "building_id" in p and p.get("building_id") > 0
        ]

        if valid_heights:
            max_height = max(valid_heights)
            min_height = min(valid_heights)
            avg_height = sum(valid_heights) / len(valid_heights)
            unique_building_ids = set(
                p["building_id"] for p in pixels.values()
                if "building_id" in p and p.get("building_id") > 0
                and "building_height" in p and p.get("building_height") != -127 and p.get("building_height") >= 0
            )

            # Store values in a dictionary
            building_data = {
                "Maximum Building Height (m)": format_value(max_height),
                "Minimum Building Height (m)": format_value(min_height),
                "Average Building Height (m)": format_value(avg_height),
                "Unique building IDs": format_value(len(unique_building_ids)),
            }
        else:
            building_data["Buildings Detected"] = "No valid building heights found"
    else:
        building_data["Buildings Detected"] = "No buildings detected"

    # Create a new window
    report_window = Toplevel(root)
    report_window.title("Domain Report")
    
    # Get the longest label for uniform width and set font style
    all_labels = list(percentages.keys()) + list(domain_data.keys()) + list(building_data.keys()) + list(geo_data.keys()) + list(tree_data.keys())
    longest_label = max(len(key.capitalize()) for key in all_labels)
    font_style = ("Courier", 12)
      
    # Display statistics
    tk.Label(report_window, text="Area shares", font=("Arial", 12), anchor="w").pack(padx=10, pady=5, fill="x")
    tk.Label(report_window, text="==================", font=("Arial", 12), anchor="w").pack(padx=10, pady=5, fill="x")
    stats_text = "\n".join([f"{key.capitalize():<{longest_label}}  {value:6.2f}%" for key, value in percentages.items()])
    tk.Label(report_window, text=stats_text, font=font_style, anchor="w", justify="left").pack(padx=10, pady=5, fill="x")

    # Display domain info
    tk.Label(report_window, text="Domain Information", font=("Arial", 12), anchor="w").pack(padx=10, pady=5, fill="x")
    domain_info_text = "\n".join([f"{key:<{longest_label}}  {value}" for key, value in domain_data.items()])
    tk.Label(report_window, text=domain_info_text, font=font_style, anchor="w", justify="left").pack(padx=10, pady=5, fill="x")
    
    # Display geo info
    geo_info_text = "\n".join([f"{key:<{longest_label}}  {value}" for key, value in geo_data.items()])
    tk.Label(report_window, text=geo_info_text, font=font_style, anchor="w", justify="left").pack(padx=10, pady=5, fill="x")

    # Display building info
    tk.Label(report_window, text="Building Information", font=("Arial", 12), anchor="w").pack(padx=10, pady=5, fill="x")
    building_info_text = "\n".join([f"{key:<{longest_label}}  {value}" for key, value in building_data.items()])
    tk.Label(report_window, text=building_info_text, font=font_style, anchor="w", justify="left").pack(padx=10, pady=5, fill="x")

    # Display tree info
    tk.Label(report_window, text="Tree Information", font=("Arial", 12), anchor="w").pack(padx=10, pady=5, fill="x")
    tree_info_text = "\n".join([f"{key:<{longest_label}}  {value}" for key, value in tree_data.items()])
    tk.Label(report_window, text=tree_info_text, font=font_style, anchor="w", justify="left").pack(padx=10, pady=5, fill="x")

    # Save report
    def save_report():
            """Save the statistics to a text file."""
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile="report.txt",
            )
            if file_path:
                with open(file_path, "w") as file:
                    file.write("Domain Report\n")
                    file.write("===============\n")
                    file.write(stats_text + "\n")
                    file.write("\n")
                    file.write("Namelist Parameter\n")
                    file.write("===============\n")
                    file.write(namelist_info + "\n")
                    file.write("\n")
                    file.write("Domain Info\n")
                    file.write("===============\n")
                    file.write(domain_info_text + "\n")
                    file.write("\n")
                    file.write(geo_info_text + "\n")
                    file.write("\n")
                    file.write("Building Information\n")
                    file.write("===============\n")
                    file.write(building_info_text + "\n")
                    file.write(f"\nBuildings detected (please switch on USM Namelist in PALM p3d)\n")
                    file.write("\n")
                    file.write("Tree Information\n")
                    file.write("===============\n")
                    file.write(tree_info_text + "\n")
                    file.write("\n")
                    file.write(f"Report generated on {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")
                messagebox.showinfo("Save Report", f"Report saved successfully to {file_path}")
        
    # Save button
    save_button = tk.Button(report_window, text="Save Report", command=save_report)
    save_button.pack(pady=10)
    
    # Close button
    tk.Button(report_window, text="Close", command=report_window.destroy).pack(pady=10)
