#!/bin/bash
# Build script for Linux executable using PyInstaller

set -e

echo "Building py-tray-command-launcher for Linux..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
pip install -r requirements-build.txt

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build dist

# Build executable
echo "Building executable with PyInstaller..."
pyinstaller py-tray-command-launcher.spec

# Check if build was successful
if [ -f "dist/py-tray-command-launcher" ]; then
    echo "Build successful!"
    echo "Executable size: $(du -h dist/py-tray-command-launcher | cut -f1)"
    echo "Testing executable..."
    QT_QPA_PLATFORM=offscreen timeout 2 ./dist/py-tray-command-launcher || echo "Test completed (expected timeout)"
else
    echo "Build failed!"
    exit 1
fi

echo "Linux executable created: dist/py-tray-command-launcher"