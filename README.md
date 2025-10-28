# Dropbox Comment Sync

**Version 0.2.0** | [GitHub](https://github.com/Oggie110/dropbox-comments) | [Handoff Doc](AGENT_HANDOFF.md) | [Menu Bar Docs](docs/MENUBAR.md)

> Automates syncing Dropbox file comment notifications from Gmail to Google Sheets

When someone comments on a Dropbox file, this tool automatically:
1. 📧 Detects the forwarded notification email in Gmail
2. 🔍 Matches the file name to your spreadsheet
3. 📝 Updates the comment and timestamp
4. ✅ Marks the email as read

**No manual copy-pasting. Just set it up once and forget it.**

## ⚡ Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/Oggie110/dropbox-comments.git
cd dropbox-comments
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your credentials

# 3. Run once to test
python -m src.sync --once --verbose

# 4. Set up auto-sync (macOS)
cp launchd/com.motive.dropbox-comments.plist.example ~/Library/LaunchAgents/com.motive.dropbox-comments.plist
# Edit plist with absolute paths
launchctl load ~/Library/LaunchAgents/com.motive.dropbox-comments.plist
```

See detailed setup instructions below ↓

## 🖥️ Menu Bar App (v0.2.0)

**NEW**: Visual menu bar interface for macOS!

```bash
# After setup, run the menu bar app instead of CLI:
python run_menubar.py
```

**Features:**
- ☁️ Cloud icon in menu bar shows sync status
- 🔄 Automatic sync every 5/10/15/30 minutes (configurable)
- 🔔 Native macOS notifications for new comments
- 📊 Quick access to Google Sheet
- 📜 View logs with one click
- ⚙️ Easy preferences management

[Full Menu Bar Documentation →](docs/MENUBAR.md)

**Note**: The menu bar app can run alongside or instead of the launchd scheduler.

## ✨ Key Features
- 📬 **Gmail monitoring** - Watches for forwarded Dropbox comment notifications
- 🎯 **Smart matching** - Fuzzy matches file names (`Artist_SongTitle.ext`) to sheet titles
- 📊 **Auto-updates** - Writes comments to column G, timestamps to column H
- 📜 **Complete history** - Logs every comment to "Comment Log" sheet
- ✅ **Deduplication** - Marks emails as read to prevent reprocessing
- ⏰ **Scheduled sync** - Runs automatically every 15 minutes (macOS launchd)

## 📋 How It Works

1. **Dropbox sends comment notification** → Your email (e.g., dropbox-notifications@example.com)
2. **Email rule forwards it** → Gmail account (e.g., oscar@oscarfogelstrom.com)
3. **Sync script runs** (every 15 min via launchd):
   - Fetches unread emails with "commented" in subject
   - Parses file name (removes `Artist_` prefix) and comment text
   - Fuzzy matches to song title in Google Sheet column D
   - Updates columns G (comment) and H (timestamp)
   - Logs to "Comment Log" sheet
   - Marks email as read

## 📦 Getting Started

### 1. Create and configure environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with your Gmail and Google Sheets credentials.

### 2. Gmail API setup (OAuth 2.0)
- Create a project in Google Cloud Console
- Enable Gmail API
- Configure OAuth consent screen
- Create OAuth 2.0 credentials (Desktop app)
- Download JSON as `credentials/oauth_credentials.json`

### 3. Google Sheets service account
1. In Google Cloud Console, create a service account
2. Enable "Google Sheets API"
3. Generate a JSON key and save as `credentials/service_account.json`
4. Share your sheet with the service account email (grant Editor access)

### 4. Email forwarding rule
Set up a forwarding rule in your Dropbox notification email account:
- Forward emails from `no-reply@dropbox.com` with subject containing "commented on"
- To: Your Gmail account (e.g., oscar@oscarfogelstrom.com)

### 5. Run the sync loop
```bash
python -m src.sync
```

Run once for testing:
```bash
python -m src.sync --once --verbose
```

### 6. Scheduling (macOS with launchd)
```bash
# Create logs directory
mkdir -p logs

# Copy plist to LaunchAgents
cp launchd/com.motive.dropbox-comments.plist.example ~/Library/LaunchAgents/com.motive.dropbox-comments.plist

# Edit the plist to update absolute paths

# Load and start
launchctl load ~/Library/LaunchAgents/com.motive.dropbox-comments.plist

# Verify it's running
launchctl list | grep dropbox-comments
```

## ⚙️ Configuration

### Environment Variables (.env)
```bash
GMAIL_USER_EMAIL=your-email@gmail.com
GMAIL_OAUTH_CREDENTIALS=./credentials/oauth_credentials.json
GMAIL_TOKEN_PATH=./credentials/gmail_token.json
GOOGLE_SHEETS_CREDENTIALS=./credentials/service_account.json
SHEET_ID=your-google-sheet-id
SHEET_RANGE=NOVA Songs!A:H
MATCH_THRESHOLD=0.85
POLL_INTERVAL_SECONDS=900
STATE_FILE=data/processed_state.json
```

### Google Sheet Structure
- **Column D**: Song titles (e.g., "Inner Bloom")
- **Column G**: Comments (updated by sync)
- **Column H**: Last update timestamp

### File Naming Convention
Dropbox files must follow the format: `Artist_SongTitle.extension`

Example: `Vera Sol_Inner Bloom.wav` → Matches "Inner Bloom" in sheet

The sync strips the artist prefix and file extension, then fuzzy matches to column D.

## 📂 Repository Layout
- `src/`: Application code
  - `gmail_client.py`: Gmail API integration and email parsing
  - `sheets_client.py`: Google Sheets API integration
  - `matcher.py`: Fuzzy matching logic for file names → song titles
  - `sync.py`: Main orchestration loop
  - `config.py`: Configuration loader
  - `state_store.py`: State persistence for processed emails
- `bin/`: Helper scripts for manual runs or scheduling
- `credentials/`: OAuth and service account credentials (git-ignored)
- `data/`: State files (git-ignored)
- `logs/`: Log files (git-ignored)
- `launchd/`: macOS launchd configuration example

## 💡 Development Notes
- Matching uses RapidFuzz's token sort ratio (default threshold: 0.85)
- Processed emails are tracked by message ID in `data/processed_state.json`
- File name normalization: `Artist_SongTitle.ext` → `song title` (lowercase, no special chars)
- Multi-paragraph comments are preserved with line breaks
- Gmail search for forwarded emails uses manual filtering (fetches unread, filters for "commented")

## 🛠️ Useful Commands

**View logs:**
```bash
tail -f logs/sync.log
```

**Stop scheduled job:**
```bash
launchctl unload ~/Library/LaunchAgents/com.motive.dropbox-comments.plist
```

**Start scheduled job:**
```bash
launchctl load ~/Library/LaunchAgents/com.motive.dropbox-comments.plist
```

**Manual test run:**
```bash
source venv/bin/activate
python -m src.sync --once --verbose
```

## 🔧 Troubleshooting

**No emails found:**
- Verify email forwarding rule is active
- Check that emails are unread in Gmail
- Ensure subject contains "commented"

**No matches found:**
- Check that song titles in column D match file names (after removing `Artist_` prefix)
- Lower `MATCH_THRESHOLD` in `.env` (try 0.70 or 0.60)
- Check "Comment Log" sheet for match scores

**Authentication errors:**
- Re-run sync to trigger OAuth flow
- Verify service account has Editor access to sheet
- Check that APIs are enabled in Google Cloud Console

## 📝 Version History

### v0.2.0 (2025-10-27)
- **NEW**: macOS menu bar application with visual feedback
- Automatic sync timer (5/10/15/30 min intervals)
- Native macOS notifications
- User preferences with JSON persistence
- Manual "Sync Now" button
- Quick access to logs and Google Sheet

### v0.1.0 (2025-10-27)
- Initial release
- Gmail-based email monitoring (replaces Dropbox API approach)
- Fuzzy matching with artist prefix handling
- Multi-paragraph comment support
- launchd scheduling for macOS
- Complete comment history logging

## 📄 License

MIT

---

**Made with Claude Code** 🤖 | Maintained by [Oscar Fogelström](https://github.com/Oggie110)
