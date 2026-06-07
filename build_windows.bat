@echo off
echo ========================================================
echo DBBackupManager - Windows Executable Builder (PyInstaller)
echo ========================================================

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Check for PyInstaller
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Install requirements
echo Installing project requirements...
pip install -r requirements.txt

:: Build the executable
echo Building DBBackupManager executable...
cd DBBackupManager

:: Create build with PyInstaller
:: --noconfirm: overwrite output directory
:: --onedir: create a one-folder bundle containing the executable
:: --windowed: do not provide a console window for standard i/o (GUI app)
:: --add-data: add necessary data files and folders
pyinstaller --noconfirm --onedir --windowed ^
    --add-data "config;config/" ^
    --name "DBBackupManager" ^
    main.py

if %errorlevel% neq 0 (
    echo Error: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo Build successful! The executable is located in DBBackupManager\dist\DBBackupManager\
echo.
pause
