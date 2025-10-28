"""
Setup script for creating macOS .app bundle with py2app.

This bundles the menu bar app into a standalone .app that:
- Has a custom app icon (instead of Python's rocket)
- Runs without needing terminal or virtual environment
- Can be added to Login Items easily

Usage:
    python setup.py py2app

Output:
    dist/Dropbox Sync.app
"""

from setuptools import setup

APP = ['run_menubar.py']
DATA_FILES = [
    ('resources', ['resources/icon_cloud.png', 'resources/README.md']),
]
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'resources/icon_cloud.png',  # App icon
    'plist': {
        'CFBundleName': 'Dropbox Sync',
        'CFBundleDisplayName': 'Dropbox Sync',
        'CFBundleIdentifier': 'com.motive.dropbox-sync',
        'CFBundleVersion': '0.2.0',
        'CFBundleShortVersionString': '0.2.0',
        'LSUIElement': True,  # Hide from Dock (menu bar app only)
        'NSHighResolutionCapable': True,
    },
    'packages': ['rumps', 'google', 'rapidfuzz', 'tenacity', 'dotenv'],
    'includes': ['AppKit'],
}

setup(
    name='Dropbox Sync',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
