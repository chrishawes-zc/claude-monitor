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
DMG_STAGING="dist/dmg-staging"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R "dist/Claude Monitor.app" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"
hdiutil create \
    -volname "Claude Monitor" \
    -srcfolder "$DMG_STAGING" \
    -ov -format UDZO \
    "Claude Monitor.dmg"
rm -rf "$DMG_STAGING"

echo ""
echo "Done! Outputs:"
echo "  App:  dist/Claude Monitor.app"
echo "  DMG:  Claude Monitor.dmg"
echo ""
echo "To install: open the DMG and drag to Applications."
