#!/usr/bin/env python3
"""Generate a simple app icon for Claude Monitor."""

import subprocess
import tempfile
import os

# Create a 1024x1024 PNG using sips-compatible approach
# We'll create it with a Python script using AppKit
ICON_SCRIPT = '''
import objc
from AppKit import (
    NSImage, NSColor, NSFont, NSBezierPath, NSMakeRect,
    NSFontAttributeName, NSForegroundColorAttributeName,
    NSBitmapImageRep, NSPNGFileType, NSGraphicsContext,
    NSCalibratedRGBColorSpace,
)
from Foundation import NSSize, NSDictionary, NSData
import sys

size = 1024
img = NSImage.alloc().initWithSize_(NSSize(size, size))
img.lockFocus()

# Dark background with rounded corners
bg_rect = NSMakeRect(0, 0, size, size)
NSColor.colorWithCalibratedRed_green_blue_alpha_(0.15, 0.15, 0.18, 1.0).set()
NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(bg_rect, 200, 200).fill()

# Draw "C" in white
font = NSFont.systemFontOfSize_(620)
attrs = {
    NSFontAttributeName: font,
    NSForegroundColorAttributeName: NSColor.whiteColor(),
}
from AppKit import NSAttributedString
text = NSAttributedString.alloc().initWithString_attributes_("C", attrs)
text_size = text.size()
x = (size - text_size.width) / 2
y = (size - text_size.height) / 2 + 20
text.drawAtPoint_((x, y))

# Draw three colored dots at the bottom
dot_y = 160
dot_r = 55
gap = 160
colors = [
    (0.2, 0.8, 0.3),   # green
    (0.2, 0.5, 1.0),   # blue
    (0.95, 0.6, 0.1),  # orange
]
for i, (r, g, b) in enumerate(colors):
    cx = size/2 + (i - 1) * gap
    NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0).set()
    dot_rect = NSMakeRect(cx - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2)
    NSBezierPath.bezierPathWithOvalInRect_(dot_rect).fill()

img.unlockFocus()

# Save as PNG
tiff_data = img.TIFFRepresentation()
bitmap = NSBitmapImageRep.imageRepWithData_(tiff_data)
png_data = bitmap.representationUsingType_properties_(NSPNGFileType, None)
png_data.writeToFile_atomically_(sys.argv[1], True)
'''

with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
    f.write(ICON_SCRIPT)
    script_path = f.name

png_path = os.path.join(os.path.dirname(__file__), "icon.png")
icns_path = os.path.join(os.path.dirname(__file__), "icon.icns")

# Generate PNG
subprocess.run(["python3", script_path, png_path], check=True)
os.unlink(script_path)

# Convert to icns via iconutil
iconset_dir = os.path.join(os.path.dirname(__file__), "icon.iconset")
os.makedirs(iconset_dir, exist_ok=True)

# Create required sizes
sizes = [16, 32, 64, 128, 256, 512, 1024]
for s in sizes:
    out = os.path.join(iconset_dir, f"icon_{s}x{s}.png")
    subprocess.run(["sips", "-z", str(s), str(s), png_path, "--out", out],
                   capture_output=True, check=True)
    # Also create @2x versions
    if s <= 512:
        out2x = os.path.join(iconset_dir, f"icon_{s//1 if s >= 32 else s}x{s//1 if s >= 32 else s}@2x.png")

# Rename to match iconutil's expected naming
import shutil
renames = {
    "icon_16x16.png": "icon_16x16.png",
    "icon_32x32.png": "icon_16x16@2x.png",
    "icon_32x32.png": "icon_32x32.png",
    "icon_64x64.png": "icon_32x32@2x.png",
    "icon_128x128.png": "icon_128x128.png",
    "icon_256x256.png": "icon_128x128@2x.png",
    "icon_256x256.png": "icon_256x256.png",
    "icon_512x512.png": "icon_256x256@2x.png",
    "icon_512x512.png": "icon_512x512.png",
    "icon_1024x1024.png": "icon_512x512@2x.png",
}

# Simpler approach: just create the right files directly
import shutil
for s in [16, 32, 128, 256, 512]:
    src = os.path.join(iconset_dir, f"icon_{s}x{s}.png")
    # Keep 1x
    # Create 2x from the next size up
    s2 = s * 2
    src2x = os.path.join(iconset_dir, f"icon_{s2}x{s2}.png")
    dst2x = os.path.join(iconset_dir, f"icon_{s}x{s}@2x.png")
    if os.path.exists(src2x) and not os.path.exists(dst2x):
        shutil.copy2(src2x, dst2x)

subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", icns_path], check=True)

# Cleanup
shutil.rmtree(iconset_dir)
os.unlink(png_path)

print(f"Created {icns_path}")
