"""User preferences management for the menu bar app."""

import json
from pathlib import Path
from typing import Any

DEFAULT_PREFS_PATH = Path.home() / ".dropbox-sync-prefs.json"

DEFAULT_PREFERENCES = {
    "sync_interval_minutes": 15,  # 5, 10, 15, or 30
    "notify_new_comments": True,
    "notify_errors": True,
    "notify_summary": False,  # Summary after each sync (can be noisy)
    "today_count": 0,  # Count of comments synced today
    "today_date": None,  # Date string (YYYY-MM-DD) for today's count
}


class Preferences:
    """Manages user preferences with JSON persistence."""

    def __init__(self, prefs_path: Path = DEFAULT_PREFS_PATH):
        self.prefs_path = prefs_path
        self._prefs = self._load()

    def _load(self) -> dict[str, Any]:
        """Load preferences from disk, or create defaults if file doesn't exist."""
        if self.prefs_path.exists():
            try:
                with open(self.prefs_path, "r") as f:
                    loaded = json.load(f)
                # Merge with defaults to handle new keys in updates
                merged = DEFAULT_PREFERENCES.copy()
                merged.update(loaded)
                return merged
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load preferences from {self.prefs_path}: {e}")
                print("Using default preferences.")
                return DEFAULT_PREFERENCES.copy()
        else:
            # First run - create default prefs file
            self._save(DEFAULT_PREFERENCES)
            return DEFAULT_PREFERENCES.copy()

    def _save(self, prefs: dict[str, Any]) -> None:
        """Save preferences to disk."""
        try:
            self.prefs_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.prefs_path, "w") as f:
                json.dump(prefs, f, indent=2)
        except IOError as e:
            print(f"Error: Could not save preferences to {self.prefs_path}: {e}")

    def save(self) -> None:
        """Save current preferences to disk."""
        self._save(self._prefs)

    @property
    def sync_interval_minutes(self) -> int:
        """Get sync interval in minutes (5, 10, 15, or 30)."""
        return self._prefs.get("sync_interval_minutes", 15)

    @sync_interval_minutes.setter
    def sync_interval_minutes(self, value: int) -> None:
        """Set sync interval in minutes. Must be one of: 5, 10, 15, 30."""
        if value not in (5, 10, 15, 30):
            raise ValueError(f"Sync interval must be 5, 10, 15, or 30 minutes, got {value}")
        self._prefs["sync_interval_minutes"] = value
        self.save()

    @property
    def notify_new_comments(self) -> bool:
        """Whether to show notifications for new comments."""
        return self._prefs.get("notify_new_comments", True)

    @notify_new_comments.setter
    def notify_new_comments(self, value: bool) -> None:
        self._prefs["notify_new_comments"] = value
        self.save()

    @property
    def notify_errors(self) -> bool:
        """Whether to show notifications for errors."""
        return self._prefs.get("notify_errors", True)

    @notify_errors.setter
    def notify_errors(self, value: bool) -> None:
        self._prefs["notify_errors"] = value
        self.save()

    @property
    def notify_summary(self) -> bool:
        """Whether to show summary notification after each sync."""
        return self._prefs.get("notify_summary", False)

    @notify_summary.setter
    def notify_summary(self, value: bool) -> None:
        self._prefs["notify_summary"] = value
        self.save()

    @property
    def today_count(self) -> int:
        """Get today's comment count."""
        return self._prefs.get("today_count", 0)

    @today_count.setter
    def today_count(self, value: int) -> None:
        """Set today's comment count."""
        self._prefs["today_count"] = value
        self.save()

    @property
    def today_date(self) -> str | None:
        """Get the date for today's count (YYYY-MM-DD)."""
        return self._prefs.get("today_date")

    @today_date.setter
    def today_date(self, value: str) -> None:
        """Set the date for today's count (YYYY-MM-DD)."""
        self._prefs["today_date"] = value
        self.save()

    def reset_to_defaults(self) -> None:
        """Reset all preferences to default values."""
        self._prefs = DEFAULT_PREFERENCES.copy()
        self.save()
