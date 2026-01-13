@echo off
REM Build script for Windows executable using PyInstaller
REM Run this script on a Windows machine with Python installed

echo Building py-tray-command-launcher for Windows...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH!
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install -r requirements-build.txt

REM Clean previous builds
echo Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build executable
echo Building executable with PyInstaller...
pyinstaller py-tray-command-launcher.spec

REM Check if build was successful
if exist "dist\py-tray-command-launcher.exe" (
    echo Build successful!
    dir dist\py-tray-command-launcher.exe
    echo Testing executable...
    timeout 2 dist\py-tray-command-launcher.exe
) else (
    echo Build failed!
    pause
    exit /b 1
)

echo Windows executable created: dist\py-tray-command-launcher.exe
pause