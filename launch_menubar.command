#!/bin/bash
# Simple launcher for Dropbox Sync menu bar app
# Double-click this file in Finder to start the app

# Set a distinctive window title so we can close this window afterwards
printf '\e]0;Dropbox Sync Launcher\a'

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the project directory and launch the menu bar app
cd "$DIR"
nohup "$DIR/venv/bin/python" "$DIR/run_menubar.py" >/dev/null 2>&1 &

# Close this temporary Terminal window if it is the launcher
osascript <<'APPLESCRIPT' >/dev/null 2>&1 &
tell application "Terminal"
	repeat with w in windows
		set tabTitle to ""
		try
			set tabTitle to custom title of w
		end try
		if tabTitle is "Dropbox Sync Launcher" or (name of w contains "Dropbox Sync Launcher") then
			close w
			exit repeat
		end if
	end repeat
end tell
APPLESCRIPT
