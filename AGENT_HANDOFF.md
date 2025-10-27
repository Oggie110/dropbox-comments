# Agent Handoff Document

## Project Overview

**dropbox-comments-sync v0.1.0** is a production automation system that syncs Dropbox file comment notifications from Gmail to a Google Sheet. The system runs autonomously every 15 minutes via macOS launchd.

## Architecture

### Core Components

1. **Gmail Client** (`src/gmail_client.py`)
   - Authenticates via OAuth 2.0
   - Fetches unread emails (searches for "commented" in subject)
   - Parses forwarded Dropbox notification emails
   - Extracts: file name, commenter, comment text, timestamp
   - Marks emails as read after processing
   - **Key challenge**: Gmail search indexing is slow for forwarded emails, so we fetch all unread and filter manually

2. **Sheets Client** (`src/sheets_client.py`)
   - Authenticates via service account
   - Reads song titles from column D
   - Updates column G (comments) and H (timestamps)
   - Creates and manages "Comment Log" sheet for history
   - Handles dynamic column sizing

3. **Matcher** (`src/matcher.py`)
   - Uses RapidFuzz for fuzzy string matching
   - Normalizes file names: `Artist_SongTitle.wav` → `song title`
   - Threshold: 0.85 (configurable)
   - Caches file→row bindings in state

4. **Sync Orchestrator** (`src/sync.py`)
   - Main entry point
   - Polls Gmail every 15 minutes (configurable)
   - Deduplicates via message IDs in state file
   - Logs all activity

5. **State Store** (`src/state_store.py`)
   - JSON-backed persistence
   - Tracks processed message IDs
   - Caches file→row mappings for performance

### Data Flow

```
Dropbox Comment → Email Notification → Forwarding Rule → Gmail
                                                            ↓
                                                    Gmail Client (fetch unread)
                                                            ↓
                                                    Parse Email (extract data)
                                                            ↓
                                                    Matcher (fuzzy match)
                                                            ↓
                                                    Sheets Client (update)
                                                            ↓
                                                    State Store (mark processed)
```

## Critical Implementation Details

### Email Parsing Challenges

**Problem**: Forwarded emails have:
- `Fwd:` prefix in subject
- Forwarding headers (`From:`, `Subject:`, `Date:`, `Message-Id:`)
- Original Dropbox notification embedded in body

**Solution**:
1. Strip `Fwd:` prefix with regex: `re.sub(r'^(Fwd:\s*)+', '', subject, flags=re.IGNORECASE)`
2. Skip forwarding headers when parsing body
3. Look for date pattern to identify comment start: `(January|February|...|December)\s+\d{1,2}`
4. Collect all lines until hitting Dropbox footer links

**Multi-paragraph comments**: Preserved by not breaking on empty lines (only break on footer markers)

### File Name Matching

**Format**: Dropbox files named `Artist_SongTitle.extension`
**Sheet**: Column D has just `SongTitle`

**Normalization** (`matcher.py:normalize_title`):
```python
# Input: "Vera Sol_Inner Bloom.wav"
# 1. Remove extension: "Vera Sol_Inner Bloom"
# 2. Split on underscore: ["Vera Sol", "Inner Bloom"]
# 3. Take after first underscore: "Inner Bloom"
# 4. Lowercase + remove special chars: "inner bloom"
# Output matches: "Inner Bloom" in sheet
```

**Fuzzy matching**: Uses `fuzz.token_sort_ratio` to handle variations in spacing/punctuation

### Gmail Search Quirk

Gmail's search API doesn't immediately index forwarded emails with exact phrase queries like `subject:"commented on"`.

**Workaround**: Fetch all unread (`is:unread`), then manually filter by checking subject contains "commented".

```python
# Fetch up to 50 unread emails
results = service.users().messages().list(userId='me', q='is:unread', maxResults=50)

# Filter for "commented"
for msg in results:
    subject = get_subject(msg)
    if 'commented' in subject.lower():
        process(msg)
```

### State Management

**File**: `data/processed_state.json`

**Schema**:
```json
{
  "processed_comment_ids": ["message_id_1", "message_id_2"],
  "file_row_cache": {
    "Vera Sol_Inner Bloom.wav": {
      "row_number": 317,
      "title": "Inner Bloom"
    }
  },
  "last_polled": "2025-10-27T10:20:00+00:00"
}
```

**Why cache file→row mappings?**
- Performance: Avoid re-matching every sync
- Consistency: If song title changes slightly, we still update the right row
- Cache invalidation: If row title changes drastically, re-match automatically

## Deployment & Operations

### Environment Setup

**Required credentials**:
1. `credentials/oauth_credentials.json` - Gmail OAuth (from Google Cloud Console)
2. `credentials/service_account.json` - Sheets service account (from Google Cloud Console)
3. `credentials/gmail_token.json` - Auto-generated on first OAuth flow

**Environment variables** (`.env`):
- `GMAIL_USER_EMAIL` - Gmail account to monitor
- `SHEET_ID` - Google Sheet ID (from URL)
- `SHEET_RANGE` - Sheet tab and range (e.g., `NOVA Songs!A:H`)
- `MATCH_THRESHOLD` - Fuzzy match threshold (0.85 = 85% similarity)
- `POLL_INTERVAL_SECONDS` - How often to check (900 = 15 min)

### Scheduling (macOS launchd)

**Config**: `~/Library/LaunchAgents/com.motive.dropbox-comments.plist`

**Key settings**:
- `StartInterval`: 900 (seconds between runs)
- `RunAtLoad`: true (start immediately on load)
- `StandardOutPath`: Logs to `logs/sync.log`
- `StandardErrorPath`: Logs to `logs/sync-error.log`

**Commands**:
```bash
# Load (start)
launchctl load ~/Library/LaunchAgents/com.motive.dropbox-comments.plist

# Unload (stop)
launchctl unload ~/Library/LaunchAgents/com.motive.dropbox-comments.plist

# Check status
launchctl list | grep dropbox-comments

# View logs
tail -f logs/sync.log
```

### Manual Testing

```bash
# Activate venv
source venv/bin/activate

# Run once with verbose output
python -m src.sync --once --verbose

# Continuous mode (runs forever)
python -m src.sync
```

## Known Issues & Limitations

1. **Gmail search lag**: Forwarded emails may not appear immediately in search results (hence the manual filtering workaround)

2. **Single artist assumption**: File names must follow `Artist_SongTitle` format with exactly one underscore separator. Files like `Artist1_Artist2_SongTitle` will fail to match (would extract `Artist2_SongTitle` instead of `SongTitle`)

3. **Unread email limit**: Currently fetches max 50 unread emails. If user has >50 unread, comment emails beyond that won't be processed. Increase `maxResults` if needed.

4. **No retry logic**: If a sync fails (network error, API quota, etc.), it doesn't retry that run. The next scheduled run will try again.

5. **OAuth token expiry**: Gmail OAuth tokens expire after ~1 week if not used. The code handles refresh automatically, but if refresh token expires, manual re-auth is required.

6. **Sheet row deletions**: If a row is deleted from the sheet, the cached mapping becomes stale. The code will re-match on next comment, but the old mapping lingers in state file.

## Future Enhancement Ideas

1. **Retry logic**: Add exponential backoff for transient failures

2. **Better artist handling**: Support multiple artists or complex file naming patterns

3. **Email notifications**: Send summary email of processed comments

4. **Web dashboard**: Simple web UI to view sync status and recent comments

5. **Multi-sheet support**: Process comments for multiple Google Sheets

6. **Comment threading**: Track conversation threads (replies to comments)

7. **Dropbox API integration**: Once Dropbox adds official comments API, switch from email parsing to direct API access

## Testing Strategy

### Unit Tests (TODO)
- Email parsing with various subject formats
- File name normalization edge cases
- Fuzzy matching accuracy

### Integration Tests (TODO)
- End-to-end: Mock Gmail → Parse → Match → Update Sheet
- OAuth flow (with mock credentials)

### Manual Testing Checklist
1. Forward a Dropbox comment email to Gmail
2. Mark as unread
3. Run `python -m src.sync --once --verbose`
4. Verify:
   - Email found and parsed correctly
   - File matched to sheet row
   - Column G updated with comment
   - Column H updated with timestamp
   - Email marked as read
   - "Comment Log" sheet has entry
   - `data/processed_state.json` updated

## Monitoring & Debugging

**Log locations**:
- `logs/sync.log` - Standard output
- `logs/sync-error.log` - Errors only

**Key log messages**:
- `"Updated row X (Title) with new comment from email Y"` - Success
- `"Could not match Dropbox file 'X' to a sheet row"` - Match failure (check threshold)
- `"No new comment emails found"` - No unread emails (normal)
- `"Sync run failed: ..."` - Fatal error (check logs)

**State file inspection**:
```bash
cat data/processed_state.json | python -m json.tool
```

**Common issues**:
- **"No emails found"** → Check forwarding rule is active, emails are unread
- **"Could not match"** → File name doesn't follow `Artist_SongTitle` format, or threshold too high
- **"Permission denied"** → Service account doesn't have Editor access to sheet
- **OAuth errors** → Re-run sync to trigger re-auth flow

## Code Quality Notes

- **Error handling**: Most exceptions are caught at the top level and logged. Individual functions may raise exceptions that are propagated.
- **Logging**: Uses Python's `logging` module. Set `--verbose` for DEBUG level.
- **Type hints**: Partial coverage (dataclasses are typed, some functions are not)
- **Documentation**: Docstrings on main classes/functions, inline comments for complex logic
- **Dependencies**: All pinned in `requirements.txt` (use `pip list --outdated` to check for updates)

## Version History

**v0.1.0 (2025-10-27)** - Initial production release
- Gmail-based email monitoring
- Fuzzy matching with artist prefix handling
- Multi-paragraph comment support
- launchd scheduling for macOS
- Complete comment history logging

## Contact & Support

**Original developer**: Claude Code (AI agent)
**Project owner**: Oscar Fogelström
**Repository**: https://github.com/Oggie110/dropbox-comments

For issues or questions, open a GitHub issue or consult this handoff document.
