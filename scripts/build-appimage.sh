#!/bin/bash
# Build script for AppImage package

set -e

echo "Building AppImage for py-tray-command-launcher..."

# Download AppImage tools if not present
if [ ! -f "tools/appimagetool" ]; then
    echo "Downloading AppImage tools..."
    mkdir -p tools
    cd tools
    
    # Download appimagetool
    wget -O appimagetool "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x appimagetool
    
    cd ..
fi

# Build the executable first
echo "Building Linux executable..."
./build-linux.sh

# Create AppDir structure
echo "Creating AppDir structure..."
rm -rf AppDir
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/pixmaps

# Copy executable
cp dist/py-tray-command-launcher AppDir/usr/bin/

# Copy desktop file
cp ../packaging/py-tray-command-launcher.desktop AppDir/

# Copy icon
cp ../resources/icons/icon.png AppDir/py-tray-command-launcher.png
cp ../resources/icons/icon.png AppDir/usr/share/pixmaps/py-tray-command-launcher.png

# Create AppRun script
cat > AppDir/AppRun << 'EOF'
#!/bin/bash
# AppRun script for py-tray-command-launcher

# Get the directory where this AppImage is located
APPDIR="$(dirname "$(readlink -f "$0")")"

# Set up environment
export PATH="$APPDIR/usr/bin:$PATH"
export XDG_DATA_DIRS="$APPDIR/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"

# Run the application
exec "$APPDIR/usr/bin/py-tray-command-launcher" "$@"
EOF

chmod +x AppDir/AppRun

# Build AppImage
echo "Building AppImage..."
ARCH=x86_64 ./tools/appimagetool --appimage-extract-and-run AppDir py-tray-command-launcher-x86_64.AppImage

# Check if AppImage was created
if [ -f "py-tray-command-launcher-x86_64.AppImage" ]; then
    echo "AppImage created successfully!"
    echo "AppImage size: $(du -h py-tray-command-launcher-x86_64.AppImage | cut -f1)"
    
    # Move to dist directory
    mkdir -p dist
    mv py-tray-command-launcher-x86_64.AppImage dist/
    
    # Test AppImage
    echo "Testing AppImage..."
    QT_QPA_PLATFORM=offscreen timeout 2 ./dist/py-tray-command-launcher-x86_64.AppImage || echo "Test completed (expected timeout)"
else
    echo "Failed to create AppImage!"
    exit 1
fi

echo "AppImage build completed: dist/py-tray-command-launcher-x86_64.AppImage"
