#!/bin/bash
# Build script for Debian package

set -e

echo "Building Debian package for py-tray-command-launcher..."

# Install required tools for building
echo "Installing Debian build tools..."
sudo apt-get update -qq
sudo apt-get install -y debhelper devscripts build-essential

# Build the executable first
echo "Building Linux executable..."
./scripts/build-linux.sh

# Create debian packaging structure
echo "Setting up Debian package structure..."
rm -rf debian
cp -r packaging/debian .

# Build the package
echo "Building Debian package..."
debuild -us -uc -b

# Check if package was created
DEB_FILE=$(ls ../py-tray-command-launcher_*.deb 2>/dev/null | head -1)
if [ -n "$DEB_FILE" ]; then
    echo "Debian package created successfully!"
    echo "Package: $DEB_FILE"
    echo "Package size: $(du -h "$DEB_FILE" | cut -f1)"
    
    # Move package to dist directory
    mkdir -p dist
    mv "$DEB_FILE" dist/
    echo "Package moved to dist/ directory"
    
    # Test package info
    echo "Package information:"
    dpkg-deb --info "dist/$(basename "$DEB_FILE")"
else
    echo "Failed to create Debian package!"
    exit 1
fi

echo "Debian package build completed."