import tkinter as tk
from tkinter import Toplevel
from tkinter import filedialog
from tkinter import messagebox
from datetime import datetime

def format_value(value, width=10):
    """Ensures integers and floats are aligned correctly."""
    if isinstance(value, int):
        return f"{value:>{width}d}"  # Right-align integers with fixed width
    elif isinstance(value, float):
        return f"{value:>{width}.2f}"  # Right-align floats with 2 decimal places
    else:
        return str(value)  # Handle non-numeric values gracefully

def generate_report(root, pixels, nx, ny, dxy, ori):
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
    namelist_info += f"dz: \n"
    
    # Domain information
    domain_data = {
    "Number of 2D Grid Cells": format_value(total_pixels),
    "Domain size x (m)": format_value(nx * dxy),
    "Domain size y (m)": format_value(ny * dxy),
    "Grid width (m)": format_value(dxy),
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
    
    building_data = {}
    if land_use_counts["building"] > 0:
        # Calculate building statistics
        max_height = max(pixel["building_height"] for pixel in pixels.values() if "building_height" in pixel)
        min_height = min(pixel["building_height"] for pixel in pixels.values() if "building_height" in pixel and pixel["building_height"] != -127)
        avg_height = sum(pixel["building_height"] for pixel in pixels.values() if "building_height" in pixel and pixel["building_height"] != -127) / land_use_counts["building"]
        unique_building_ids = set(pixel["building_id"] for pixel in pixels.values() if "building_id" in pixel and pixel["building_height"] != -127)

        # Store values in a dictionary
        building_data = {
            "Maximum Building Height (m)": format_value(max_height),
            "Minimum Building Height (m)": format_value(min_height),
            "Average Building Height (m)": format_value(avg_height),
            "Unique building IDs": format_value(len(unique_building_ids)),
        }
    else:
        building_data["Buildings Detected"] = "No buildings detected"

    # Create a new window
    report_window = Toplevel(root)
    report_window.title("Domain Report")
    
    # Get the longest label for uniform width and set font style
    all_labels = list(percentages.keys()) + list(domain_data.keys()) + list(building_data.keys()) + list(geo_data.keys())
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
                    file.write(f"Report generated on {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}\n")
                messagebox.showinfo("Save Report", f"Report saved successfully to {file_path}")
        
    # Save button
    save_button = tk.Button(report_window, text="Save Report", command=save_report)
    save_button.pack(pady=10)
    
    # Close button
    tk.Button(report_window, text="Close", command=report_window.destroy).pack(pady=10)