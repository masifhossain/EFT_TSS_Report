# Taxi Statements (Portable App)

This package can be built into a Windows app that non-technical users can run by double-clicking an EXE. The app opens automatically in the browser.

## Build (developer)
1. Double-click `build_exe.bat` or run it in PowerShell.
2. When finished, you'll get `dist/TaxiStatements/TaxiStatements.exe` and its folder contents.

## Share with users
- Share the entire folder `dist/TaxiStatements/` (zip it before uploading to Google Drive).
- Users should download, unzip, then double-click `TaxiStatements.exe`.

## Run (end users)
1. Open the folder you received (e.g., `TaxiStatements/`).
2. Double-click `TaxiStatements.exe`.
3. Your browser will open automatically at `http://127.0.0.1:5000/`.
4. Upload CSVs and generate reports. PDFs will appear in the `output/` folder next to the EXE.

## Notes
- The app stores uploads in `uploads/` and generated PDFs in `output/` next to the EXE.
- If Windows SmartScreen warns about an unknown publisher, click **More info** → **Run anyway**.
- If the browser doesn't open automatically, open `http://127.0.0.1:5000/` manually.
