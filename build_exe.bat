@echo off
setlocal

REM Build portable onedir exe for Taxi Statements app
pushd %~dp0

echo Building portable TaxiStatements executable...

if not exist .venv (
  echo Creating virtual environment...
  py -3 -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Installing/updating dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo Cleaning previous build...
if exist "dist\TaxiStatements" rmdir /s /q "dist\TaxiStatements"
if exist "build" rmdir /s /q "build"
if exist "TaxiStatements.spec" del "TaxiStatements.spec"

echo Building executable with PyInstaller...
pyinstaller --noconfirm --clean --name "TaxiStatements" --onedir ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  app.py

if exist "dist\TaxiStatements\TaxiStatements.exe" (
  echo.
  echo ========================================
  echo Build completed successfully!
  echo ========================================
  echo.
  echo Executable location: dist\TaxiStatements\TaxiStatements.exe
  echo.
  echo To distribute:
  echo 1. Zip the entire folder: dist\TaxiStatements\
  echo 2. Share the zip file
  echo.
  echo To test:
  echo 1. Double-click dist\TaxiStatements\TaxiStatements.exe
  echo 2. The app will open in your browser automatically
  echo.
) else (
  echo.
  echo ========================================
  echo Build FAILED!
  echo ========================================
  echo Check the output above for errors.
)

pause

popd
endlocal
