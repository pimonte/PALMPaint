# PALMPaint – A Lightweight Pixel-Art Tool for PALM Static Drivers
PALMPaint is a simple tool for creating PALM Static Drivers. Instead of manually generating static drivers from python scripts for small idealized cases, just paint your area — no prior knowledge required.

With experienced PALM users who need quick test setups in mind, it is also for new users looking for an easy introduction to static drivers and for everyone who has fun with it.

![Logo](/Pictures/palmpaint_screenshot_small.png)

## Key Features

**Define Your Area** – Set nx, ny, and grid width before you start
**Paint Land Surfaces** – Use preset tools for:
- Vegetation
- Pavement
- Water
- Buildings
- Single trees

Grid Coordinates Displayed in Meters & Grid Points – Paint precisely where you need
Cell info – hover over any grid cell to see terrain height, surface type, soil type, building attributes, water temperature, and resolved-vegetation data (tree height, LAD, BAD, tree ID)
Save in NetCDF Format – Ready-to-go static driver format
Edit Later – Save and reload projects in JSON format
Try Loading Existing Static Drivers – Modify what you’ve already created! (Maybe, if it works...)

---

# Tree Tool & Tree Generator

## Single Tree Tool

Select the **single_tree** tool in the toolbar to place individual resolved trees.  
Each tree is painted as a full 3D LAD (Leaf Area Density) volume and — when BAD writing is enabled — a matching 3D BAD (Basal Area Density) volume. Both arrays appear in the tree overlay (toggle with **Ctrl+T**).

### Top-bar controls

| Control | Description |
|---|---|
| **Species** | Select a preset tree species; loads default geometry and LAD/BAD parameters |
| **Shape** | Crown shape (Spherical, Cylindrical, Conical, Inv. Conical, Paraboloid, Inv. Paraboloid) |
| **H/D ratio** | Crown aspect ratio: crown\_height / crown\_diameter; larger = taller crown |
| **Crown Diam. (m)** | Horizontal crown diameter; also sets the hover-footprint preview circle |
| **Tree Height (m)** | Total tree height from ground to crown tip |
| **LAI** | Leaf Area Index (m²/m²) — scales the total leaf area |
| **BAD/LAD** | BAD-to-LAD ratio — controls branch area density relative to leaf area density |
| **Trunk Diam. (m)** | Trunk diameter at breast height |
| **Write BAD** | Checkbox — when checked, the `bad` array is written to the NetCDF output |

**Left-click** places a tree. **Right-click** (or right-drag) removes the tree(s) under the cursor.

### BAD field

The Basal Area Density field captures the aerodynamic drag of woody branches and the trunk (not implemented in PALM yet):

- **Trunk and sub-crown stem**: BAD is set to **1.0 m²/m³** from ground level to mid-crown height. The trunk contribution is only written when the trunk diameter is at least one grid cell wide.
- **Crown interior** (`palm_extinction` model): BAD is inversely proportional to LAD — lowest where leaf density is highest (near the crown surface) and highest towards the crown interior. Maximum crown BAD equals `bad_lad_ratio`.
- **Crown** (`beta_density` model): BAD is proportional to LAD — highest where leaf density is highest. Maximum crown BAD equals `bad_lad_ratio`.

---

## Tree Generator *(alpha)*

> **⚠ Alpha feature** — The Tree Generator is an early-stage addition and may produce unexpected results for edge-case parameter combinations. The interface and the generated output will be refined in future versions.

The **Tree Generator…** button (visible when the single_tree tool is active) opens an advanced dialog that replaces the simple ellipsoid crown model with a 3D LAD field based on various distribution functions. This way, you can create your own tree for your specific case and get an idea of what it will look like in PALM based on your grid spacing.

### Opening the Dialog

1. Select the **single_tree** tool.
2. Click **Tree Generator…** in the top bar.
3. Configure parameters (see below).
4. Click **Apply to Brush** — the status label switches to **Generator: active** and the spinboxes in the top bar are synced.
5. Paint trees as usual — each new tree will use the generator output.

Click **Clear Generator** to revert to the simple ellipsoid mode.

### Parameters

**Geometry**

| Parameter | Description |
|---|---|
| Max height (m) | Total tree height H from ground to crown tip |
| Crown diameter (m) | Horizontal crown diameter Dc; also defines the LAI reference area π·(Dc/2)² |
| Trunk diameter (m) | Trunk diameter below the crown |
| Crown aspect (H/D) | Ratio crown_height / crown_diameter (PALM convention); larger = taller crown |
| Crown shape | Crown shape ID (1–6): Spherical, Cylindrical, Conical, Inv. Conical, Paraboloid, Inv. Paraboloid |

**LAD Model**

| Parameter | Description |
|---|---|
| LAD model | `beta_density` — Beta-PDF vertical profile (default); `palm_extinction` — PALM-style radial extinction |
| Profile mode | `Beta / Markkanen (2003)` — Beta profile modulates LAD crown shape is fixed; `Geometrie (Beta-Form)` — Beta profile modulates the crown cross-section, LAD is constant |
| Alpha / Beta | Shape parameters of the Beta(α, β) distribution controlling the vertical LAD profile |
| Extinction k | Decay constant for `palm_extinction` mode (corresponds to PALM's `tree_sphere_extinction`) |
| BAD/LAD ratio | Maximum branch area density in the crown relative to LAD (m²/m³) |

**Scaling** — exactly one of the following must be active:

| Control | Description |
|---|---|
| LAI (m²/m²) | Total leaf area relative to the crown projection area |
| LAD_max (m²/m³) | Peak volumetric leaf area density |

Use the radio buttons to switch between the two; the inactive field is greyed out.

### Preview

If **matplotlib** is installed in the active Python environment, the right panel shows a live 2×3 preview grid (max-Z projection, vertical cross-sections, and three horizontal XY slices through the crown) rendered at 1 m resolution.  
Without matplotlib the panel displays an install hint; the generator still works fully — the preview is purely cosmetic.

To install matplotlib:
```bash
pip install matplotlib
# or with conda:
conda install matplotlib
```

### Presets

- **Save Preset** — saves all current parameters to a JSON file (default location: `~/.config/palmpaint/presets/`).
- **Load Preset** — loads a previously saved JSON preset and repopulates all controls.

Preset files are plain JSON dictionaries and can be edited by hand or shared between users.

---

##  Limitations & Performance

Not Optimized for Large Areas – Best for small test cases up to 512 x 512 grid points
Minimal Dependencies – Runs (hopefully) on any computer without effort

## Development & Contribution

PALMPaint is a hobby project built for learning and experimenting with GUI python programming. It’s not a stable release yet, and many features could be added in the future — when time allows and interest exists.

This project is open-source. PALMPaint is licensed under the **GNU General Public License v3.0**.  
See the [LICENSE](LICENSE) file for details. Feel free to fork it, modify it if you like the idea. Due to time constraints, I cannot guarantee regular updates or support, but I hope you find it useful!

# Installation Guide for PALMPaint

The only dependency required for all core functionalities is NumPy. Therefore, no installation is necessary.
The program should run for most PALM users just by switching to the palmpaint folder and type in your terminal:

```bash
python3 palmpaint.py
```

It is developed on Ubuntu and never tested on a Windows machine.

---

The recommended installation method is via **Conda**, but you can also use **pip** in your existing environment or a virtual environment. Additional dependencies will be required in the future to support new features.

## 1. Installing with Conda (Recommended)

If you don’t have **Conda**, install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/products/distribution) first.

Then, create a Conda environment and install PALMPaint:

```bash
conda env create -f environment.yml
conda activate palmpaint_env
python3 palmpaint.py
```

## 2. Installing with Pip (Existing Python Environment)

If you already have Python installed, you can install dependencies using `pip`:

```bash
pip install -r requirements.txt
python3 palmpaint.py
```

This installs the required dependencies **globally**. If you want a clean, isolated setup, use a **virtual environment** instead (see below).

---

## 3. Installing in a New Virtual Environment (Pip)

To avoid dependency conflicts, it's best to install PALMPaint in a **virtual environment**:

### Using `venv` (Built-in Virtual Environments)

1. Create a new virtual environment:
   ```bash
   python -m venv palmpaint_venv
   ```
2. Activate it:
     ```bash
     source venv/bin/activate
     ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run PALMPaint:
   ```bash
   python3 palmpaint.py
   ```



