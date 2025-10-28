# Building Standalone .app Bundle

This guide explains how to build a standalone macOS `.app` bundle that:
- Uses a custom icon (instead of Python's rocket)
- Doesn't require terminal or activating virtualenv
- Can be launched like any macOS app
- Has proper notifications with custom icon

## Quick Build

```bash
# Install py2app if not already installed
pip install py2app

# Build the app
python setup.py py2app

# The app will be in dist/
open dist/
```

The output will be: `dist/Dropbox Sync.app`

## Running the .app

**Option 1: Double-click**
- Open `dist/Dropbox Sync.app` in Finder
- Cloud icon appears in menu bar

**Option 2: Add to Login Items**
1. Open **System Preferences** → **Users & Groups** → **Login Items**
2. Click **+** button
3. Navigate to `dist/Dropbox Sync.app`
4. Add it

**Option 3: Move to Applications**
```bash
cp -r "dist/Dropbox Sync.app" /Applications/
```

## Custom Icon

The app uses `resources/icon_cloud.png` as its icon. This shows in:
- Dock (if LSUIElement is disabled)
- Notifications
- Activity Monitor
- Login Items

To change the icon:
1. Replace `resources/icon_cloud.png` with your custom icon (22x22 or larger)
2. Rebuild: `python setup.py py2app`

For a proper macOS `.icns` icon:
```bash
# Create .icns from PNG
mkdir MyIcon.iconset
sips -z 16 16     icon_cloud.png --out MyIcon.iconset/icon_16x16.png
sips -z 32 32     icon_cloud.png --out MyIcon.iconset/icon_16x16@2x.png
sips -z 32 32     icon_cloud.png --out MyIcon.iconset/icon_32x32.png
sips -z 64 64     icon_cloud.png --out MyIcon.iconset/icon_32x32@2x.png
sips -z 128 128   icon_cloud.png --out MyIcon.iconset/icon_128x128.png
sips -z 256 256   icon_cloud.png --out MyIcon.iconset/icon_128x128@2x.png
iconutil -c icns MyIcon.iconset
# Update setup.py: 'iconfile': 'MyIcon.icns'
```

## Benefits of .app Bundle

**vs. Python script (`python run_menubar.py`)**:
- ✅ Custom icon in notifications (not Python rocket)
- ✅ No need to open Terminal
- ✅ No need to activate virtualenv
- ✅ Can be added to Login Items easily
- ✅ Looks professional in Activity Monitor
- ✅ All dependencies bundled inside
- ❌ Larger file size (~50-100MB)
- ❌ Needs rebuild after code changes

**vs. launchd plist**:
- ✅ Visual in Login Items (not hidden)
- ✅ Easy to quit/restart from menu bar
- ✅ User-friendly for non-technical users
- ✅ Can coexist with launchd

## Troubleshooting

**"App is damaged" error on first launch**
```bash
xattr -cr "dist/Dropbox Sync.app"
```

**App won't start (no icon appears)**
- Check Console.app for errors
- Ensure `.env` file is in same directory as app
- Credentials must be at relative paths from app location

**Notifications still show Python rocket**
- Quit all instances of the app
- Rebuild with py2app
- Clear notification permissions:
  - System Preferences → Notifications → Remove Python entry
  - Launch app again to re-request permissions

**App says "missing module"**
- Add missing module to `packages` in setup.py
- Rebuild

## Development Workflow

When developing, use the Python script for faster iteration:
```bash
python run_menubar.py
```

When releasing or testing the full UX:
```bash
python setup.py py2app
open "dist/Dropbox Sync.app"
```

## Distribution

To share the app:
1. Build: `python setup.py py2app`
2. Compress: `cd dist && zip -r "Dropbox Sync.zip" "Dropbox Sync.app"`
3. Share the .zip file

**Note**: Recipients will need to:
- Have their own `.env` and credentials files
- Configure OAuth credentials
- May need to allow app in System Preferences → Security

For production distribution, consider:
- Code signing with Apple Developer ID
- Notarization for Gatekeeper
- DMG installer with instructions
