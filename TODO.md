# dropbox-comments - TODO List

**Status:** Released (v0.2.0) - Production use
**Priority:** Low - Maintenance & enhancements

---

## 🐛 Bug Fixes & Stability

### Known Issues
- [ ] Monitor for any sync failures
- [ ] Check for edge cases in fuzzy matching
- [ ] Test with very long comment text
- [ ] Verify behavior with special characters in filenames

### Error Handling
- [ ] Improve error notifications
- [ ] Add retry logic for failed syncs
- [ ] Better handling of Gmail API rate limits
- [ ] Handle Google Sheets API errors gracefully

---

## ✨ Enhancements

### Menu Bar App Improvements
- [ ] Add more sync interval options (1 min, 45 min, 60 min)
- [ ] Quick toggle to pause/resume syncing
- [ ] Show last sync time in menu
- [ ] Better error status indicators

### Functionality
- [ ] Support multiple Google Sheets
- [ ] Filter which Dropbox folders to monitor
- [ ] Custom column mapping (not just G and H)
- [ ] Export comment history to CSV

### Notifications
- [ ] Customize notification settings
- [ ] Sound options
- [ ] Group multiple comments
- [ ] Notification history

---

## 📊 Monitoring & Analytics

### Usage Tracking
- [ ] Log sync statistics
- [ ] Track match accuracy rates
- [ ] Monitor API usage
- [ ] Performance metrics

### Reporting
- [ ] Weekly summary of synced comments
- [ ] Failed sync report
- [ ] Most commented files

---

## 📚 Documentation

### User Guide
- [ ] Update README with v0.2.0 features
- [ ] Add troubleshooting guide
- [ ] Create setup video/GIF
- [ ] Document all menu bar options

### Developer Docs
- [ ] Code documentation
- [ ] Architecture overview
- [ ] API integration details

---

## 🔮 Future Features

### Advanced Matching
- [ ] Machine learning for better filename matching
- [ ] Handle file renames
- [ ] Track file history

### Integrations
- [ ] Slack notifications
- [ ] Discord webhooks
- [ ] Email summaries
- [ ] iOS companion app

### Multi-User Support
- [ ] Share comment logs with team
- [ ] Multiple user profiles
- [ ] Permission management

---

## 🔥 Immediate Next Actions

**Build Standalone .app Bundle (v0.2.0):**
- [ ] Install py2app: `pip install py2app`
- [ ] Build app: `python setup.py py2app`
- [ ] Test `dist/Dropbox Sync.app` launches correctly
- [ ] Verify custom cloud icon appears (not Python rocket)
- [ ] Test adding to Login Items
- [ ] Test notifications show custom icon
- [ ] Move to Applications folder for daily use
- [ ] Document any issues or configuration needed

**Maintenance Mode:**
- [ ] Monitor for issues in production use
- [ ] Keep dependencies updated
- [ ] Review logs periodically

**When Time Permits:**
- [ ] Pick 1-2 small enhancements
- [ ] Improve error handling
- [ ] Update documentation

---

## 📝 Notes

- App is working well in production
- Focus on stability over new features
- Most enhancements are "nice to have"
- Primary value: Saves manual copy-paste time

---

*Last updated: 2025-10-28*
