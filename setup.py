from setuptools import setup

APP = ["claude-monitor-menubar.py"]

DATA_FILES = []

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "icon.icns",
    "packages": ["rumps", "objc", "AppKit", "Foundation"],
    "plist": {
        "CFBundleName": "Claude Monitor",
        "CFBundleDisplayName": "Claude Monitor",
        "CFBundleIdentifier": "com.claudemonitor.menubar",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSUIElement": True,  # Hide from Dock — menu bar only
        "NSHumanReadableCopyright": "Claude Monitor",
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
