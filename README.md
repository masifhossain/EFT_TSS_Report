# Taxi Statements Generator

Generate printable EFTPOS and Taxi Service Subsidy (TSS) statements from CSV input files via a simple local web app. The project bundles a Flask backend, ReportLab-powered PDF generation, and a PyInstaller build script for creating a portable Windows executable.

## Features

- Upload multiple raw CSV exports and group them automatically per taxi.
- Produce two report styles:
  - **EFTPOS statement** with detailed payment breakdowns.
  - **Taxi TSS statement** with the simplified six-column layout.
- Landscape A4 PDF output with branding, period headers, and totals.
- Portable build (`TaxiStatements.exe`) that end users can double-click without installing Python.

## Project layout

```
app.py                # Flask application and upload/report endpoints
report_generator.py    # CSV parsing and ReportLab PDF rendering
static/                # Branding assets (e.g., logo.png)
templates/             # HTML templates for the web UI
dist/                  # PyInstaller build output (ignored by git)
build_exe.bat          # Convenience script to rebuild the executable
requirements.txt       # Python dependencies
```

The folders `uploads/`, `output/`, `dist/`, `build/`, and `Raw Data/` are ignored by git so you can keep local data and builds without committing them.

## Prerequisites

- Windows with PowerShell (build script targets Windows on x64).
- Python 3.13 (or edit the virtual environment to use another supported version).
- [Git](https://git-scm.com/) for version control.

## Getting started

```powershell
# clone the repo once it exists on GitHub
git clone https://github.com/<your-account>/<repo-name>.git
cd <repo-name>

# create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# install dependencies
pip install -r requirements.txt

# run the Flask dev server
python app.py
```

Navigate to <http://127.0.0.1:5000> to upload CSV files and generate PDFs. Output files are written to the `output/` directory.

## Building the portable executable

```powershell
.\.venv\Scripts\Activate.ps1
.\build_exe.bat
```

The launcher `TaxiStatements.exe` will be placed in `dist\TaxiStatements\`. Zip that folder, move it to another machine, and double-click the executable to run the app.

## Creating the GitHub repository

1. Sign in to GitHub and create a new **empty** repository (no README or .gitignore) named whatever you prefer.
2. In this project folder, initialise git and make the first commit:

    ```powershell
    cd "C:\EFT TSS Report Programming"
    git init
    git add .
    git commit -m "Initial commit"
    ```

3. Add the GitHub remote and push:

    ```powershell
    git remote add origin https://github.com/<your-account>/<repo-name>.git
    git branch -M main
    git push -u origin main
    ```

Replace `<your-account>` and `<repo-name>` with your GitHub username and repository name. After pushing, the code will appear on GitHub for collaborators or deployment pipelines.

---

If you want sample CSV files for demos, copy them into `Raw Data/` locally—they will stay out of version control thanks to the `.gitignore` entry.
