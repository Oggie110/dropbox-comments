# Menu Bar App Documentation

**Version 0.2.0**

The Dropbox Comment Sync menu bar app provides a visual interface for monitoring the sync process on macOS.

## Features

- **Visual Status Indicator**: Cloud icon in the menu bar shows sync status at a glance
- **Automatic Sync Timer**: Configurable interval (5, 10, 15, or 30 minutes)
- **Manual Sync**: Trigger sync on-demand via "Sync Now" button
- **Native Notifications**: macOS Notification Center alerts for new comments and errors
- **Today's Count**: See how many comments were synced today
- **Quick Actions**: Open Google Sheet, view logs, adjust preferences
- **Preferences**: Customize sync interval and notification settings

## Installation

### Prerequisites

The menu bar app requires all the same setup as the CLI version:
- Python 3.8+
- Gmail API credentials
- Google Sheets service account
- Email forwarding rule configured

See main [README.md](../README.md) for setup instructions.

### Additional Dependencies

Install `rumps` (if not already installed):

```bash
source venv/bin/activate
pip install -r requirements.txt
```

## Running the App

### Simple Launch

```bash
source venv/bin/activate
python run_menubar.py
```

The cloud icon will appear in your menu bar.

### Running at Login (Optional)

To have the app start automatically when you log in:

**Option 1: System Preferences (Recommended)**
1. Open **System Preferences** → **Users & Groups** → **Login Items**
2. Click the **+** button
3. Navigate to the project directory
4. Select `run_menubar.py`
5. Click **Add**

**Option 2: Create an App Bundle (Advanced)**

For a more native experience, you can use `py2app` to create a standalone `.app` bundle:

```bash
pip install py2app
python setup.py py2app
```

(Note: `setup.py` configuration for py2app not included in v0.2.0 - coming in future release)

## Menu Items

When you click the cloud icon, you'll see:

```
☁️
─────────────────────────
Status: Last synced at 14:32
Today: 3 comments
─────────────────────────
Sync Now
View Logs
Open Sheet
─────────────────────────
Preferences
About
─────────────────────────
Quit
```

### Status Line

Shows current sync status:
- **"Status: Idle"** - App is running but no sync has occurred yet
- **"Status: Syncing..."** - Sync is currently in progress
- **"Status: Last synced at HH:MM"** - Last successful sync time
- **"Status: Error (see logs)"** - Last sync failed

### Today's Count

Shows how many new comments were synced today (resets at midnight).

### Sync Now

Triggers an immediate sync, bypassing the automatic timer.

### View Logs

Opens the `logs/` directory in Finder. View detailed sync logs here.

### Open Sheet

Opens your Google Sheet in the default web browser.

### Preferences

Adjust sync settings:
- **Sync Interval**: Choose 5, 10, 15, or 30 minutes
- **Notifications**: (Future) Toggle notification types

### About

Shows app version and credits.

### Quit

Stops the sync worker and exits the app.

## Notifications

The app sends macOS notifications for:

### New Comments (Enabled by Default)

When new comments are synced:
```
New Dropbox Comment
Artist_SongTitle.wav
"Great work on the intro..."
```

### Errors (Enabled by Default)

When sync fails:
```
Dropbox Sync Error
Failed to sync comments
Connection timeout...
```

### Summary (Disabled by Default)

After each sync (can be noisy):
```
Dropbox Sync Complete
3 new comments synced in 2.5s
```

## Preferences File

User preferences are stored in:
```
~/.dropbox-sync-prefs.json
```

Default preferences:
```json
{
  "sync_interval_minutes": 15,
  "notify_new_comments": true,
  "notify_errors": true,
  "notify_summary": false
}
```

You can manually edit this file if needed.

## Architecture

### Threading Model

The menu bar app uses a multi-threaded architecture:

1. **Main Thread** (UI Thread)
   - Runs the `rumps.App` event loop
   - Updates menu items and icon
   - Displays notifications
   - Non-blocking

2. **Worker Thread** (Sync Thread)
   - Runs sync operations in the background
   - Communicates results via `Queue`
   - Never blocks the UI

3. **Communication**
   - Worker → UI: `Queue` with `SyncResult` objects
   - UI → Worker: Thread-safe event flags (`manual_sync_event`)
   - UI polls queue every 0.5 seconds via `rumps.Timer`

### Key Components

```
src/
├── menu_bar_app.py       # Main UI (DropboxSyncApp)
├── sync_worker.py        # Background sync thread
├── notifications.py      # macOS notification wrappers
├── preferences.py        # Settings persistence
└── [existing modules]    # Reused from CLI version
```

### Flow Diagram

```
┌─────────────────────────────────────────┐
│  Menu Bar (Main Thread)                 │
│  - Display status                       │
│  - Handle button clicks                 │
│  - Poll result queue (0.5s timer)       │
└────────┬────────────────────────────────┘
         │
         │ Queue (SyncResult)
         │
┌────────▼────────────────────────────────┐
│  Sync Worker (Background Thread)        │
│  - Timer-based sync (5/10/15/30 min)    │
│  - Manual sync trigger                  │
│  - Calls run_once() from sync.py        │
└─────────────────────────────────────────┘
```

## Coexistence with launchd

The menu bar app can run alongside the existing launchd scheduled job:

- **Menu bar app**: Provides visual feedback and manual control
- **launchd job**: Continues to run on schedule as backup

Both use the same state file (`data/processed_state.json`), so:
- ✅ No duplicate processing (emails marked as read are skipped)
- ✅ Either can be disabled independently
- ⚠️ They don't coordinate - both will sync if running simultaneously

### Recommended Setup

**Development/Active Use:**
- Run menu bar app only
- Disable launchd temporarily:
  ```bash
  launchctl unload ~/Library/LaunchAgents/com.motive.dropbox-comments.plist
  ```

**Production/Unattended:**
- Run launchd only (lightweight, no UI overhead)
- Or run both for redundancy

## Troubleshooting

### App Won't Start

**Error: "Failed to load configuration"**
- Check that `.env` file exists and is properly configured
- Verify credential files exist at paths specified in `.env`

**Error: "No module named 'rumps'"**
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

**Error: "FileNotFoundError: [Errno 2] No such file or directory: '☁️'"**
- **Cause**: rumps treats `icon` parameter as a file path, not a string
- **Solution**: The app now uses `title="☁️"` instead of `icon="☁️"`
- **If you encounter this**: Update to latest version from feature branch
- **For custom PNG icons**: Use `icon="path/to/file.png"` instead of `title`

**Error: "NSInternalInconsistencyException - Item to be inserted into menu already is in another menu"**
- **Cause**: Custom quit button conflicts with rumps' built-in quit button
- **Solution**: Don't override quit button, let rumps handle it automatically
- **Fixed in**: Latest commit on feature/menu-bar-app branch

### Notifications Not Appearing

1. Check **System Preferences** → **Notifications** → **Python** (or **Terminal**)
2. Ensure notifications are allowed
3. Verify preferences: `cat ~/.dropbox-sync-prefs.json`

### Sync Not Running

1. Check status line in menu - does it say "Error"?
2. View logs: Click **View Logs** in menu
3. Try manual sync: Click **Sync Now**
4. Check Gmail and Sheets credentials are valid

### "Today's Count" Not Resetting

The count resets at midnight. If it seems stuck:
- Restart the app
- Check system clock is correct

### Icon Not Changing

Currently the app uses a static cloud emoji (☁️) for all states. To use custom colored icons:
1. Add PNG files to `resources/` directory (see `resources/README.md`)
2. Update `menu_bar_app.py` to load PNG icons instead of emoji

## Known Limitations

### Version 0.2.0

- **Icon**: Uses emoji (☁️) instead of custom colored PNG icons
  - **Why**: rumps treats `icon` parameter as file path; emoji must use `title` parameter
  - **Implication**: Icon color doesn't change to indicate status (stays constant)
  - **Future**: Can add PNG icons to `resources/` and switch to `icon` parameter
- **Preferences UI**: Basic alert dialogs instead of proper settings window
- **Notification settings**: Can't toggle notification types from UI (must edit JSON)
- **Last sync time**: Only shows time, not date (for older syncs)
- **Manual credential reload**: Not yet implemented in UI
- **No tray tooltip**: Icon doesn't show hover text

### Planned Improvements (v0.3.0)

- Custom colored PNG icons (gray/yellow/green/red)
- Rich preferences window with checkboxes for all settings
- "Reload Credentials" menu item
- Detailed status tooltip on icon hover
- "View Comment Log" menu item (opens sheet directly to log tab)
- Auto-update check

## Development

### Testing

Run the app in verbose logging mode:

```bash
source venv/bin/activate
python run_menubar.py
```

Logs will appear in the terminal. To test:

1. Click **Sync Now** - should see "Manual sync triggered" in logs
2. Wait for automatic sync - should occur at configured interval
3. Check notifications appear for new comments
4. Verify "Today's Count" increments

### Debugging

Add debug logging to any module:

```python
import logging
logging.debug("Debug message: %s", some_variable)
```

Then run with verbose logging:

```bash
python -m src.menu_bar_app --verbose
```

(Note: Verbose flag not yet implemented in menu bar launcher)

### Making Changes

The app hot-reloads on restart. After making code changes:
1. Click **Quit** in menu
2. Run `python run_menubar.py` again

## Integration with CLI

The menu bar app **reuses all existing sync logic** from the CLI version:

- Same `run_once()` function
- Same Gmail and Sheets clients
- Same state management
- Same configuration

This means:
- Bug fixes to sync logic benefit both CLI and menu bar app
- You can switch between CLI and menu bar seamlessly
- State is shared (processed emails, file→row cache)

The only new code is the UI layer (`menu_bar_app.py`, `sync_worker.py`, `notifications.py`, `preferences.py`).

## FAQ

**Q: Can I run multiple instances?**
A: Not recommended. They'll share the same state file and credentials, which may cause conflicts.

**Q: Does this replace the launchd job?**
A: Not yet. They can coexist. Future versions may include auto-management of launchd.

**Q: Can I customize the icon?**
A: Yes! Add PNG files to `resources/` and update `menu_bar_app.py`. See `resources/README.md`.

**Q: Does this work on Windows/Linux?**
A: No, `rumps` is macOS-only. The CLI version works on all platforms.

**Q: Will this drain my battery?**
A: The app is very lightweight (mostly idle), but the timer wakes up every 0.5s to check the queue. Battery impact is minimal.

**Q: Can I change the sync interval dynamically?**
A: Yes! Click **Preferences** and choose a new interval. Takes effect immediately.

---

**Need Help?** See [AGENT_HANDOFF.md](../AGENT_HANDOFF.md) for technical architecture details or [README.md](../README.md) for general setup.
