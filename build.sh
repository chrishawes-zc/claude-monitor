#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "==> Setting up build environment..."
python3 -m venv .venv-build
source .venv-build/bin/activate
pip install -q rumps py2app pyobjc-framework-Cocoa

echo "==> Generating icon..."
python generate_icon.py

echo "==> Building app..."
rm -rf build dist
python setup.py py2app

echo "==> Ad-hoc code signing..."
codesign --force --deep --sign - "dist/Claude Monitor.app"

echo "==> Creating DMG..."
rm -f "Claude Monitor.dmg"
hdiutil create \
    -volname "Claude Monitor" \
    -srcfolder "dist/Claude Monitor.app" \
    -ov -format UDZO \
    "Claude Monitor.dmg"

echo ""
echo "Done! Outputs:"
echo "  App:  dist/Claude Monitor.app"
echo "  DMG:  Claude Monitor.dmg"
echo ""
echo "To install: open the DMG and drag to Applications."
