#!/bin/bash
# Main build script for all package formats

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== py-tray-command-launcher Build Script ==="
echo "Building all supported package formats..."
echo

# Parse command line arguments
BUILD_LINUX=true
BUILD_DEB=true
BUILD_APPIMAGE=true
CLEAN_FIRST=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --linux-only)
            BUILD_DEB=false
            BUILD_APPIMAGE=false
            shift
            ;;
        --deb-only)
            BUILD_LINUX=false
            BUILD_APPIMAGE=false
            shift
            ;;
        --appimage-only)
            BUILD_LINUX=false
            BUILD_DEB=false
            shift
            ;;
        --clean)
            CLEAN_FIRST=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --linux-only    Build only Linux executable"
            echo "  --deb-only      Build only Debian package"
            echo "  --appimage-only Build only AppImage"
            echo "  --clean         Clean build directories first"
            echo "  --help          Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Clean if requested
if [ "$CLEAN_FIRST" = true ]; then
    echo "Cleaning build directories..."
    rm -rf build dist AppDir debian tools
    echo "Clean completed."
    echo
fi

# Build Linux executable
if [ "$BUILD_LINUX" = true ]; then
    echo "=== Building Linux Executable ==="
    ./scripts/build-linux.sh
    echo
fi

# Build Debian package
if [ "$BUILD_DEB" = true ]; then
    echo "=== Building Debian Package ==="
    ./scripts/build-deb.sh
    echo
fi

# Build AppImage
if [ "$BUILD_APPIMAGE" = true ]; then
    echo "=== Building AppImage ==="
    ./scripts/build-appimage.sh
    echo
fi

# Summary
echo "=== Build Summary ==="
if [ -d "dist" ]; then
    echo "Built packages:"
    ls -lh dist/
    echo
    echo "Total packages: $(ls dist/ | wc -l)"
else
    echo "No packages were built."
fi

echo
echo "For Windows builds, run scripts/build-windows.bat on a Windows machine."
echo "Build completed!"