# PALMPaint

Paint static drivers for the [PALM](https://www.palm-model.org) model instead of scripting them. Draw buildings, trees, streets and water on a grid, or load an existing driver and edit it.

![PALMPaint](/Pictures/palmpaint_screenshot_small.png)

## Install

You need Python 3.12 or newer (tested with 3.12 and 3.14) and the PALMPaint folder.

**With conda (recommended)**

```bash
conda env create -f environment.yml
conda activate palmpaint_env
conda install -c conda-forge matplotlib pyvista     # optional extras
```

**With pip**

```bash
python -m venv palmpaint_venv
source palmpaint_venv/bin/activate      # Windows: palmpaint_venv\Scripts\activate
pip install -r requirements.txt
pip install matplotlib pyvista          # optional extras
```

The optional extras add the Tree Generator preview and the Analysis Plots (matplotlib) and the 3D View (pyvista). Everything else works without them.

## Start

```bash
python palmpaint.py                  # welcome screen: new project or load
python palmpaint.py driver.nc        # open a static driver directly
```

| Option | What it does |
|---|---|
| `--ram 32` | RAM in GB PALMPaint may use (default 8). Larger arrays go into the `tmp/` folder. |
| `--backend tk` | Slow fallback drawing, if Pillow does not work |
| `--experimental` | Also show unfinished brushes (irrigation, shf, ssws) |

## What you can do

- Paint vegetation, pavement, water, buildings and single trees. Terrain height in the heightmap view, soil in the soil view.
- Load and edit drivers from palm_csd, palmgeo, palmpy and other tools. The project file is the NetCDF static driver itself.
- Check a driver against PALM's rules (Extras, Validate), clean it, and preview PALM's topography filter (Filter Sweep).
- Look at it: Analysis Plots and a 3D View.
- Trees: see [docs/trees.md](docs/trees.md) for the tree tool and the Tree Generator (alpha).

Undo is Ctrl+Z. The select tool shows its keyboard shortcuts in the top bar.

## Good to know

- Developed and tested on Ubuntu. Windows is untested.
- Large domains (e.g. 2048 x 2048 cells) work but need memory. Use `--ram` to match your computer.
- Everything tiny on a high-resolution screen? conda-forge's Python comes with Tk 8.6, which ignores the desktop scaling.

## License

PALMPaint is free software under the GNU General Public License v3, see [LICENSE](LICENSE).

It is shared in the hope that it is useful, but WITHOUT ANY WARRANTY: there is no guarantee that it works correctly or that it fits a particular purpose. Check the static drivers it creates before you use them for simulations. See the GNU General Public License for the details.

PALMPaint is a hobby project. Feel free to fork it. I can't promise regular updates or support.
