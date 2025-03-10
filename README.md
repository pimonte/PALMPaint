# PALMPaint – A Lightweight Pixel-Art Tool for PALM Static Drivers
PALMPaint is a simple tool for creating PALM Static Drivers. Instead of manually generating static drivers from python scripts for small idealized cases, just paint your area — no prior knowledge required.

With experienced PALM users who need quick test setups in mind, it is also for new users looking for an easy introduction to static drivers and for everyone who has fun with it.

![Logo](/Pictures/palmpaint_screenshot_small.png)

## Key Features

**Define Your Area** – Set nx, ny, and grid width before you start
**Paint Land Surfaces** – Use preset tools for:
- Short Grass
- Bare Soil
- Pavement
- Water
- Buildings

Grid Coordinates Displayed in Meters & Grid Points – Paint precisely where you need
Save in NetCDF Format – Ready-to-go static driver format
Edit Later – Save and reload projects in JSON format
Try Loading Existing Static Drivers – Modify what you’ve already created! (Maybe, if it works...)

##  Limitations & Performance

Not Optimized for Large Areas – Best for small test cases up to 256 x 256 grid points
Minimal Dependencies – Runs (hopefully) on any computer without effort

## Development & Contribution

PALMPaint is a hobby project built for learning and experimenting with GUI python programming. It’s not a stable release yet, and many features could be added in the future — when time allows and interest exists.

This project is open-source. PALMPaint is licensed under the **GNU General Public License v3.0**.  
See the [LICENSE](LICENSE) file for details. Feel free to fork it, modify it if you like the idea. Due to time constraints, I cannot guarantee regular updates or support, but I hope you find it useful!

# Installation Guide for PALMPaint

The recommended installation method is via **Conda**, but you can also use **pip** in your existing environment or a virtual environment. Since only very few modules are loaded, the program should run for most PALM users just by switching to the palmpaint folder and type in your terminal:

```bash
python3 palmpaint.py
```

It is developed on Ubuntu and never tested on a Windows machine.

---

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

---

